BEGIN;

SET LOCAL TIME ZONE 'UTC';

DO $$
BEGIN
    IF current_database() <> 'shop_lab' THEN
        RAISE EXCEPTION 'Expected database shop_lab, connected to %', current_database();
    END IF;
END;
$$;

CREATE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_status CHECK (status IN ('ACTIVE', 'SUSPENDED'))
);

CREATE TABLE products (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    name VARCHAR(200) NOT NULL,
    price NUMERIC(12, 2) NOT NULL,
    stock_quantity INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_products PRIMARY KEY (id),
    CONSTRAINT ck_products_price_non_negative CHECK (price >= 0),
    CONSTRAINT ck_products_stock_non_negative CHECK (stock_quantity >= 0),
    CONSTRAINT ck_products_status CHECK (status IN ('DRAFT', 'ACTIVE', 'INACTIVE'))
);

CREATE TABLE orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT,
    status VARCHAR(20) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_orders PRIMARY KEY (id),
    CONSTRAINT fk_orders_user_id
        FOREIGN KEY (user_id)
        REFERENCES users (id)
        ON UPDATE RESTRICT
        ON DELETE SET NULL,
    CONSTRAINT ck_orders_status
        CHECK (status IN ('PENDING', 'PAID', 'PREPARING', 'SHIPPED', 'COMPLETED', 'CANCELLED')),
    CONSTRAINT ck_orders_total_non_negative CHECK (total_amount >= 0)
);

CREATE TABLE order_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_order_items PRIMARY KEY (id),
    CONSTRAINT fk_order_items_order_id
        FOREIGN KEY (order_id)
        REFERENCES orders (id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    CONSTRAINT fk_order_items_product_id
        FOREIGN KEY (product_id)
        REFERENCES products (id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    CONSTRAINT uq_order_items_order_product UNIQUE (order_id, product_id),
    CONSTRAINT ck_order_items_unit_price_non_negative CHECK (unit_price >= 0),
    CONSTRAINT ck_order_items_quantity_positive CHECK (quantity >= 1)
);

CREATE TABLE payments (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    order_id BIGINT NOT NULL,
    transaction_id VARCHAR(100) NOT NULL,
    method VARCHAR(20) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_payments PRIMARY KEY (id),
    CONSTRAINT fk_payments_order_id
        FOREIGN KEY (order_id)
        REFERENCES orders (id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    CONSTRAINT uq_payments_transaction_id UNIQUE (transaction_id),
    CONSTRAINT ck_payments_method CHECK (method IN ('CARD', 'BANK_TRANSFER')),
    CONSTRAINT ck_payments_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_payments_status CHECK (status IN ('PENDING', 'SUCCEEDED', 'FAILED', 'CANCELLED'))
);

CREATE TABLE reviews (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    order_item_id BIGINT NOT NULL,
    rating SMALLINT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_reviews PRIMARY KEY (id),
    CONSTRAINT fk_reviews_order_item_id
        FOREIGN KEY (order_item_id)
        REFERENCES order_items (id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    CONSTRAINT uq_reviews_order_item_id UNIQUE (order_item_id),
    CONSTRAINT ck_reviews_rating_range CHECK (rating BETWEEN 1 AND 5)
);

CREATE TABLE legal_retention_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    order_id BIGINT NOT NULL,
    retention_category VARCHAR(30) NOT NULL,
    retained_data_encrypted BYTEA NOT NULL,
    retention_until TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_legal_retention_records PRIMARY KEY (id),
    CONSTRAINT fk_legal_retention_records_order_id
        FOREIGN KEY (order_id)
        REFERENCES orders (id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    CONSTRAINT uq_legal_retention_records_order_category UNIQUE (order_id, retention_category),
    CONSTRAINT ck_legal_retention_records_category
        CHECK (retention_category IN ('CONTRACT', 'PAYMENT', 'DISPUTE'))
);

CREATE UNIQUE INDEX idx_payments_one_success_per_order
    ON payments (order_id)
    WHERE status = 'SUCCEEDED';

CREATE TRIGGER trg_users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_products_set_updated_at
BEFORE UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_orders_set_updated_at
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_payments_set_updated_at
BEFORE UPDATE ON payments
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_reviews_set_updated_at
BEFORE UPDATE ON reviews
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;
