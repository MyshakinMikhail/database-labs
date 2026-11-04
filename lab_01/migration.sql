-- Дополнительное требование ЛР 1: справочник и история статусов заказа.
-- Применяется один раз после schema.sql и data.sql, без пересоздания БД.
\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE order_statuses (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    CONSTRAINT ck_order_statuses_code_not_blank CHECK (btrim(code) <> ''),
    CONSTRAINT ck_order_statuses_name_not_blank CHECK (btrim(name) <> '')
);

INSERT INTO order_statuses (code, name) VALUES
    ('open', 'Открыт'),
    ('closed', 'Закрыт'),
    ('cancelled', 'Отменён');

-- Значения статусов и все существующие заказы сохраняются.
ALTER TABLE orders RENAME COLUMN status TO status_code;
ALTER TABLE orders DROP CONSTRAINT ck_orders_status;
ALTER TABLE orders ADD CONSTRAINT fk_orders_status
    FOREIGN KEY (status_code) REFERENCES order_statuses (code) ON DELETE RESTRICT;

CREATE TABLE order_status_history (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id INT NOT NULL,
    status_code TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_backfilled BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_order_status_history_order FOREIGN KEY (order_id)
        REFERENCES orders (id) ON DELETE RESTRICT,
    CONSTRAINT fk_order_status_history_status FOREIGN KEY (status_code)
        REFERENCES order_statuses (code) ON DELETE RESTRICT
);

-- Старые переходы неизвестны: фиксируется снимок на момент миграции,
-- а не вымышленное время первоначального получения статуса.
INSERT INTO order_status_history (order_id, status_code, is_backfilled)
SELECT id, status_code, TRUE FROM orders ORDER BY id;

CREATE FUNCTION record_order_status_change() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status_code IS DISTINCT FROM OLD.status_code THEN
        INSERT INTO order_status_history (order_id, status_code)
        VALUES (NEW.id, NEW.status_code);
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_record_order_status_change
AFTER INSERT OR UPDATE OF status_code ON orders
FOR EACH ROW EXECUTE FUNCTION record_order_status_change();

COMMIT;

