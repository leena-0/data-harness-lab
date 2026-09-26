#!/usr/bin/env python3
"""Measure PostgreSQL query plans repeatedly through the local Docker Compose DB."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from pathlib import Path
from typing import Any


LAB_DIR = Path(__file__).resolve().parents[1]
COMPOSE_FILE = LAB_DIR / "docker-compose.yml"
WARMUP_RUNS = 5
MEASURED_RUNS = 10

ORDER_NORMAL = """
SELECT orders.id, orders.status, orders.total_amount, orders.created_at
FROM orders
WHERE orders.user_id = (
    SELECT id FROM users WHERE email = 'bench-user-05000@example.com'
)
ORDER BY orders.created_at DESC
LIMIT 20
"""

ORDER_HOT = """
SELECT orders.id, orders.status, orders.total_amount, orders.created_at
FROM orders
WHERE orders.user_id = (
    SELECT id FROM users WHERE email = 'bench-user-09999@example.com'
)
ORDER BY orders.created_at DESC
LIMIT 20
"""

PRODUCT_ACTIVE = """
SELECT products.id, products.name, products.price,
       products.stock_quantity, products.created_at
FROM products
WHERE products.status = 'ACTIVE'
ORDER BY products.created_at DESC
LIMIT 20
"""

CANDIDATES = {
    "order_user_only": (
        "CREATE INDEX bench_idx_orders_user ON orders (user_id)",
        "DROP INDEX bench_idx_orders_user",
        (("order_normal", ORDER_NORMAL), ("order_hot", ORDER_HOT)),
        "bench_idx_orders_user",
    ),
    "order_user_created": (
        "CREATE INDEX bench_idx_orders_user_created "
        "ON orders (user_id, created_at DESC)",
        "DROP INDEX bench_idx_orders_user_created",
        (("order_normal", ORDER_NORMAL), ("order_hot", ORDER_HOT)),
        "bench_idx_orders_user_created",
    ),
    "product_status_created": (
        "CREATE INDEX bench_idx_products_status_created "
        "ON products (status, created_at DESC)",
        "DROP INDEX bench_idx_products_status_created",
        (("product_active", PRODUCT_ACTIVE),),
        "bench_idx_products_status_created",
    ),
    "product_active_partial": (
        "CREATE INDEX bench_idx_products_active_created "
        "ON products (created_at DESC) WHERE status = 'ACTIVE'",
        "DROP INDEX bench_idx_products_active_created",
        (("product_active", PRODUCT_ACTIVE),),
        "bench_idx_products_active_created",
    ),
}

FINAL_SCENARIOS = (
    ("order_normal", ORDER_NORMAL),
    ("order_hot", ORDER_HOT),
    ("product_active", PRODUCT_ACTIVE),
)


def psql(sql: str) -> str:
    command = [
        "docker",
        "compose",
        "-f",
        str(COMPOSE_FILE),
        "exec",
        "-T",
        "postgres",
        "psql",
        "-X",
        "-qAt",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "lab",
        "-d",
        "shop_lab",
        "-c",
        sql,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def explain(query: str) -> dict[str, Any]:
    output = psql(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}")
    return json.loads(output)[0]


def walk_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [node]
    for child in node.get("Plans", []):
        nodes.extend(walk_nodes(child))
    return nodes


def summarize(plan: dict[str, Any]) -> dict[str, Any]:
    root = plan["Plan"]
    nodes = walk_nodes(root)
    return {
        "planning_ms": float(plan["Planning Time"]),
        "execution_ms": float(plan["Execution Time"]),
        "shared_hit": int(root.get("Shared Hit Blocks", 0)),
        "shared_read": int(root.get("Shared Read Blocks", 0)),
        "rows_removed": sum(
            int(node.get("Rows Removed by Filter", 0)) for node in nodes
        ),
        "node_types": sorted({str(node["Node Type"]) for node in nodes}),
        "sort_methods": sorted(
            {
                str(node["Sort Method"])
                for node in nodes
                if "Sort Method" in node
            }
        ),
    }


def median_result(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "planning_ms": statistics.median(r["planning_ms"] for r in results),
        "execution_ms": statistics.median(r["execution_ms"] for r in results),
        "shared_hit": statistics.median(r["shared_hit"] for r in results),
        "shared_read": statistics.median(r["shared_read"] for r in results),
        "rows_removed": statistics.median(r["rows_removed"] for r in results),
        "node_types": results[-1]["node_types"],
        "sort_methods": results[-1]["sort_methods"],
    }


def measure(label: str, candidate: str, query: str, index_bytes: int) -> dict[str, Any]:
    for _ in range(WARMUP_RUNS):
        explain(query)
    measured = [summarize(explain(query)) for _ in range(MEASURED_RUNS)]
    result = median_result(measured)
    result.update(
        {
            "scenario": label,
            "candidate": candidate,
            "index_bytes": index_bytes,
        }
    )
    return result


def index_size(index_name: str) -> int:
    return int(psql(f"SELECT pg_relation_size('{index_name}')"))


def reset_benchmark_indexes() -> None:
    psql(
        "DROP INDEX IF EXISTS bench_idx_orders_user;"
        "DROP INDEX IF EXISTS bench_idx_orders_user_created;"
        "DROP INDEX IF EXISTS bench_idx_products_status_created;"
        "DROP INDEX IF EXISTS bench_idx_products_active_created;"
    )


def ensure_data() -> None:
    count = int(
        psql(
            "SELECT count(*) FROM orders WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'bench-user-%@example.com')"
        )
    )
    if count < 100000:
        raise RuntimeError("Generate at least 100,000 benchmark orders first")


def ensure_final_indexes_absent() -> None:
    count = int(
        psql(
            "SELECT count(*) FROM pg_indexes WHERE schemaname = 'public' "
            "AND indexname IN "
            "('idx_orders_user_created_at', 'idx_products_active_created_at')"
        )
    )
    if count:
        raise RuntimeError("Roll back 002 final indexes before candidate comparison")


def ensure_final_indexes_present() -> None:
    count = int(
        psql(
            "SELECT count(*) FROM pg_indexes WHERE schemaname = 'public' "
            "AND indexname IN "
            "('idx_orders_user_created_at', 'idx_products_active_created_at')"
        )
    )
    if count != 2:
        raise RuntimeError("Apply 002 final indexes before final measurement")


def run_candidates() -> list[dict[str, Any]]:
    ensure_final_indexes_absent()
    reset_benchmark_indexes()
    results = [
        measure("order_normal", "baseline", ORDER_NORMAL, 0),
        measure("order_hot", "baseline", ORDER_HOT, 0),
        measure("product_active", "baseline", PRODUCT_ACTIVE, 0),
    ]

    try:
        for candidate, (create, drop, scenarios, index_name) in CANDIDATES.items():
            psql(create)
            psql("ANALYZE orders; ANALYZE products")
            size = index_size(index_name)
            for scenario, query in scenarios:
                results.append(measure(scenario, candidate, query, size))
            psql(drop)
    finally:
        reset_benchmark_indexes()
    return results


def run_final() -> list[dict[str, Any]]:
    ensure_final_indexes_present()
    sizes = {
        "order_normal": index_size("idx_orders_user_created_at"),
        "order_hot": index_size("idx_orders_user_created_at"),
        "product_active": index_size("idx_products_active_created_at"),
    }
    return [
        measure(scenario, "final", query, sizes[scenario])
        for scenario, query in FINAL_SCENARIOS
    ]


def print_markdown(results: list[dict[str, Any]]) -> None:
    print(
        "| scenario | candidate | planning ms | execution ms | "
        "hit/read | rows removed | nodes | sort | index bytes |"
    )
    print("|---|---|---:|---:|---:|---:|---|---|---:|")
    for result in results:
        nodes = ", ".join(result["node_types"])
        sorts = ", ".join(result["sort_methods"]) or "-"
        print(
            f"| {result['scenario']} | {result['candidate']} | "
            f"{result['planning_ms']:.3f} | {result['execution_ms']:.3f} | "
            f"{result['shared_hit']:.0f}/{result['shared_read']:.0f} | "
            f"{result['rows_removed']:.0f} | {nodes} | {sorts} | "
            f"{result['index_bytes']} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("candidates", "final"), default="candidates")
    args = parser.parse_args()

    ensure_data()
    results = run_candidates() if args.mode == "candidates" else run_final()
    print_markdown(results)


if __name__ == "__main__":
    main()
