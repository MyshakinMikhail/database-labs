BEGIN;

INSERT INTO staff (full_name, email, role) VALUES
    ('Анна Иванова', 'anna.ivanova@restaurant.example', 'waiter'),
    ('Борис Петров', 'boris.petrov@restaurant.example', 'waiter'),
    ('Мария Соколова', 'maria.sokolova@restaurant.example', 'manager');

INSERT INTO dining_tables (table_number, seats) VALUES
    (1, 2),
    (2, 4),
    (3, 4),
    (4, 6);

INSERT INTO menu_categories (name) VALUES
    ('Закуски'),
    ('Основные блюда'),
    ('Напитки');

INSERT INTO menu_items (category_id, name, price, is_available)
SELECT c.id, src.name, src.price, TRUE
FROM (VALUES
    ('Закуски', 'Брускетта', 350.00),
    ('Закуски', 'Цезарь', 480.00),
    ('Закуски', 'Сырная тарелка', 620.00),
    ('Основные блюда', 'Паста', 690.00),
    ('Основные блюда', 'Стейк', 1450.00),
    ('Основные блюда', 'Ризотто', 720.00),
    ('Напитки', 'Чай', 220.00),
    ('Напитки', 'Лимонад', 300.00),
    ('Напитки', 'Кофе', 250.00)
) AS src(category_name, name, price)
JOIN menu_categories AS c ON c.name = src.category_name;

INSERT INTO orders (order_number, table_id, staff_id, opened_at, status)
SELECT src.order_number, t.id, s.id, src.opened_at::TIMESTAMPTZ, src.status
FROM (VALUES
    ('R-101', 1, 'anna.ivanova@restaurant.example', '2026-10-05 12:00:00+03', 'closed'),
    ('R-102', 2, 'boris.petrov@restaurant.example', '2026-10-05 13:30:00+03', 'closed'),
    ('R-103', 3, 'anna.ivanova@restaurant.example', '2026-10-06 18:00:00+03', 'closed'),
    ('R-104', 4, 'boris.petrov@restaurant.example', '2026-10-06 19:15:00+03', 'open'),
    ('R-105', 1, 'maria.sokolova@restaurant.example', '2026-10-07 14:00:00+03', 'closed')
) AS src(order_number, table_number, staff_email, opened_at, status)
JOIN dining_tables AS t ON t.table_number = src.table_number
JOIN staff AS s ON s.email = src.staff_email;

INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price)
SELECT o.id, mi.id, src.quantity, src.unit_price
FROM (VALUES
    ('R-101', 'Закуски', 'Брускетта', 1, 350.00),
    ('R-101', 'Основные блюда', 'Паста', 2, 690.00),
    ('R-101', 'Напитки', 'Чай', 2, 220.00),
    ('R-102', 'Закуски', 'Цезарь', 1, 480.00),
    ('R-102', 'Основные блюда', 'Стейк', 1, 1450.00),
    ('R-102', 'Напитки', 'Лимонад', 2, 300.00),
    ('R-103', 'Закуски', 'Сырная тарелка', 1, 620.00),
    ('R-103', 'Основные блюда', 'Ризотто', 1, 720.00),
    ('R-103', 'Напитки', 'Кофе', 2, 250.00),
    ('R-104', 'Основные блюда', 'Паста', 1, 690.00),
    ('R-104', 'Напитки', 'Чай', 1, 220.00),
    ('R-105', 'Закуски', 'Брускетта', 2, 350.00),
    ('R-105', 'Основные блюда', 'Стейк', 1, 1450.00)
) AS src(order_number, category_name, item_name, quantity, unit_price)
JOIN orders AS o ON o.order_number = src.order_number
JOIN menu_categories AS c ON c.name = src.category_name
JOIN menu_items AS mi ON mi.category_id = c.id AND mi.name = src.item_name;

INSERT INTO payments (order_id, amount, method, paid_at)
SELECT o.id, src.amount, src.method, src.paid_at::TIMESTAMPTZ
FROM (VALUES
    ('R-101', 1000.00, 'cash', '2026-10-05 13:00:00+03'),
    ('R-101', 1170.00, 'card', '2026-10-05 13:01:00+03'),
    ('R-102', 2530.00, 'card', '2026-10-05 14:30:00+03'),
    ('R-103', 1840.00, 'cash', '2026-10-06 19:15:00+03'),
    ('R-105', 2150.00, 'card', '2026-10-07 15:00:00+03')
) AS src(order_number, amount, method, paid_at)
JOIN orders AS o ON o.order_number = src.order_number;

COMMIT;
