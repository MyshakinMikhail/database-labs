-- Задание 1.1. Расширение исходной базы ресторана из ЛР 1.
-- Запускать после lab_01/schema.sql и lab_01/data.sql.
-- Повторный запуск не добавляет дубликаты и не изменяет исходные строки.
BEGIN;

-- Необязательное пожелание гостя: NULL означает отсутствие пожелания.
-- В исходной модели все столбцы обязательны, поэтому для примера NULL
-- добавляется предметно осмысленный атрибут без изменения старых данных.
ALTER TABLE orders ADD COLUMN IF NOT EXISTS guest_note TEXT;

INSERT INTO staff (full_name, email, role) VALUES
    ('Дмитрий Смирнов', 'dmitry.smirnov@restaurant.example', 'waiter'),
    ('Елена Орлова', 'elena.orlova@restaurant.example', 'waiter')
ON CONFLICT (email) DO NOTHING;

-- Нижняя и верхняя допустимые границы вместимости. Столик 6 без заказов.
INSERT INTO dining_tables (table_number, seats) VALUES (5, 1), (6, 20)
ON CONFLICT (table_number) DO NOTHING;

INSERT INTO menu_categories (name) VALUES ('Десерты'), ('Сезонное меню')
ON CONFLICT (name) DO NOTHING;

INSERT INTO menu_items (category_id, name, price, is_available)
SELECT c.id, src.name, src.price, src.is_available
FROM (VALUES
    ('Десерты', 'Чизкейк', 520.00, TRUE),
    ('Десерты', 'Мороженое', 300.00, TRUE),
    ('Десерты', 'Панна-котта', 440.00, TRUE),
    ('Сезонное меню', 'Тыквенный суп', 390.00, FALSE)
) AS src(category_name, name, price, is_available)
JOIN menu_categories AS c ON c.name = src.category_name
ON CONFLICT (category_id, name) DO NOTHING;

-- 12 заказов в каждом из трёх месяцев: всего 36 новых заказов.
-- Дни 4, 8, 12: отменены; 6, 10: открыты; остальные: закрыты.
INSERT INTO orders (order_number, table_id, staff_id, opened_at, status, guest_note)
SELECT
    'L2-' || to_char(month_start, 'YYYYMM') || '-' || lpad(day_no::TEXT, 2, '0'),
    t.id,
    s.id,
    (month_start::DATE + (day_no - 1) + TIME '12:00'
        + (day_no % 4) * INTERVAL '1 hour') AT TIME ZONE 'Europe/Moscow',
    CASE WHEN day_no IN (4, 8, 12) THEN 'cancelled'
         WHEN day_no IN (6, 10) THEN 'open'
         ELSE 'closed' END,
    CASE WHEN day_no = 1 THEN 'Подать напитки до основного блюда'
         WHEN day_no = 10 THEN 'Счёт оплачивается частями'
         ELSE NULL END
FROM (VALUES (DATE '2026-08-01'), (DATE '2026-09-01'), (DATE '2026-10-01'))
    AS months(month_start)
CROSS JOIN generate_series(1, 12) AS days(day_no)
JOIN dining_tables AS t ON t.table_number = 1 + (day_no - 1) % 5
JOIN staff AS s ON s.email = CASE day_no % 3
    WHEN 1 THEN 'anna.ivanova@restaurant.example'
    WHEN 2 THEN 'boris.petrov@restaurant.example'
    ELSE 'dmitry.smirnov@restaurant.example' END
ON CONFLICT (order_number) DO NOTHING;

-- По три позиции в заказе. Заказы 04 и 06 намеренно без позиций.
-- Цена продажи копируется в unit_price и далее не зависит от цен меню.
INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price)
SELECT o.id, mi.id, dish.quantity, mi.price
FROM orders AS o
CROSS JOIN LATERAL (SELECT right(o.order_number, 2)::INT AS day_no) AS d
CROSS JOIN LATERAL (VALUES
    ('Основные блюда', CASE d.day_no % 3
        WHEN 0 THEN 'Паста' WHEN 1 THEN 'Стейк' ELSE 'Ризотто' END,
        1 + d.day_no % 2),
    ('Напитки', CASE d.day_no % 3
        WHEN 0 THEN 'Чай' WHEN 1 THEN 'Кофе' ELSE 'Лимонад' END, 2),
    (CASE WHEN d.day_no % 2 = 1 THEN 'Закуски' ELSE 'Десерты' END,
     CASE WHEN d.day_no % 2 = 1 THEN 'Брускетта'
          WHEN d.day_no IN (2, 8) THEN 'Мороженое' ELSE 'Чизкейк' END, 1)
) AS dish(category_name, item_name, quantity)
JOIN menu_categories AS c ON c.name = dish.category_name
JOIN menu_items AS mi ON mi.category_id = c.id AND mi.name = dish.item_name
WHERE o.order_number ~ '^L2-2026(08|09|10)-(0[1-9]|1[0-2])$'
  AND d.day_no NOT IN (4, 6)
ON CONFLICT (order_id, menu_item_id) DO NOTHING;

-- День 02: две оплаты одного заказа; 03 и 10: половина суммы;
-- 09: закрытый заказ без оплаты (ошибка бизнес-процесса);
-- отменённые заказы и пустой открытый заказ оплат не имеют.
WITH order_totals AS (
    SELECT o.id, o.opened_at, right(o.order_number, 2)::INT AS day_no,
           SUM(oi.quantity * oi.unit_price) AS total
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.id
    WHERE o.order_number ~ '^L2-2026(08|09|10)-(0[1-9]|1[0-2])$'
    GROUP BY o.id
)
INSERT INTO payments (order_id, amount, method, paid_at)
SELECT ot.id, planned.amount, planned.method, planned.paid_at
FROM order_totals AS ot
CROSS JOIN LATERAL (
    SELECT
        CASE WHEN ot.day_no = 2 THEN ROUND(ot.total * 0.40, 2)
             WHEN ot.day_no IN (3, 10) THEN ROUND(ot.total * 0.50, 2)
             ELSE ot.total END,
        CASE WHEN ot.day_no IN (2, 5) THEN 'cash' ELSE 'card' END,
        ot.opened_at + INTERVAL '1 hour'
    WHERE ot.day_no IN (1, 2, 3, 5, 7, 10, 11)
    UNION ALL
    SELECT ot.total - ROUND(ot.total * 0.40, 2), 'card',
           ot.opened_at + INTERVAL '1 hour 5 minutes'
    WHERE ot.day_no = 2
) AS planned(amount, method, paid_at)
WHERE NOT EXISTS (SELECT 1 FROM payments AS p WHERE p.order_id = ot.id);

COMMIT;
