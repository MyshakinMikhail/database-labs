CREATE TABLE staff (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    CONSTRAINT uq_staff_email UNIQUE (email),
    CONSTRAINT ck_staff_full_name_not_blank CHECK (btrim(full_name) <> ''),
    CONSTRAINT ck_staff_role CHECK (role IN ('waiter', 'manager'))
);

CREATE TABLE dining_tables (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_number INTEGER NOT NULL,
    seats SMALLINT NOT NULL,
    CONSTRAINT uq_dining_tables_number UNIQUE (table_number),
    CONSTRAINT ck_dining_tables_number_positive CHECK (table_number > 0),
    CONSTRAINT ck_dining_tables_seats CHECK (seats BETWEEN 1 AND 20)
);

CREATE TABLE menu_categories (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    CONSTRAINT uq_menu_categories_name UNIQUE (name),
    CONSTRAINT ck_menu_categories_name_not_blank CHECK (btrim(name) <> '')
);

CREATE TABLE menu_items (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_id INT NOT NULL,
    name TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_menu_items_category FOREIGN KEY (category_id)
        REFERENCES menu_categories (id) ON DELETE RESTRICT,
    CONSTRAINT uq_menu_items_category_name UNIQUE (category_id, name),
    CONSTRAINT ck_menu_items_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_menu_items_price_positive CHECK (price > 0)
);

CREATE TABLE orders (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_number TEXT NOT NULL,
    table_id INT NOT NULL,
    staff_id INT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'open',
    -- historyStatusId INT NOT NULL,
    CONSTRAINT uq_orders_number UNIQUE (order_number),
    CONSTRAINT fk_orders_table FOREIGN KEY (table_id)
        REFERENCES dining_tables (id) ON DELETE RESTRICT,
    CONSTRAINT fk_orders_staff FOREIGN KEY (staff_id)
        REFERENCES staff (id) ON DELETE RESTRICT,
    CONSTRAINT ck_orders_number_not_blank CHECK (btrim(order_number) <> ''),
    CONSTRAINT ck_orders_status CHECK (status IN ('open', 'closed', 'cancelled'))
);

CREATE TABLE order_items (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id INT NOT NULL,
    menu_item_id INT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    CONSTRAINT fk_order_items_order FOREIGN KEY (order_id)
        REFERENCES orders (id) ON DELETE RESTRICT,
    CONSTRAINT fk_order_items_menu_item FOREIGN KEY (menu_item_id)
        REFERENCES menu_items (id) ON DELETE RESTRICT,
    CONSTRAINT uq_order_items_order_menu_item UNIQUE (order_id, menu_item_id),
    CONSTRAINT ck_order_items_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_order_items_unit_price_positive CHECK (unit_price > 0)
);

CREATE TABLE payments (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id INT NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    method TEXT NOT NULL,
    paid_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_payments_order FOREIGN KEY (order_id)
        REFERENCES orders (id) ON DELETE RESTRICT,
    CONSTRAINT ck_payments_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_payments_method CHECK (method IN ('cash', 'card'))
);
