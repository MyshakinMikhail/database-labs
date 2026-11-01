-- Задание 1.2. Все демонстрационные изменения отменяются в конце.
-- Снимок строк проверяет ROLLBACK. Последовательности IDENTITY, как принято
-- в PostgreSQL, не откатываются; пропуски идентификаторов допустимы.
CREATE TEMP TABLE lab02_dml_snapshot AS
SELECT
    (SELECT jsonb_agg(to_jsonb(s) ORDER BY s.id) FROM staff AS s) AS staff_rows,
    (SELECT jsonb_agg(to_jsonb(m) ORDER BY m.id) FROM menu_items AS m) AS menu_rows,
    (SELECT jsonb_agg(to_jsonb(o) ORDER BY o.id) FROM orders AS o) AS order_rows,
    (SELECT jsonb_agg(to_jsonb(i) ORDER BY i.id) FROM order_items AS i) AS item_rows;

BEGIN;

-- 1. Новая сущность (сотрудник), его заказ и две связанные позиции.
INSERT INTO staff (full_name, email, role)
VALUES ('Тестовый официант', 'lab02.demo@restaurant.example', 'waiter')
RETURNING id, full_name;

INSERT INTO orders (order_number, table_id, staff_id, opened_at, status, guest_note)
SELECT 'L2-DML-DEMO', t.id, s.id, TIMESTAMPTZ '2026-10-15 12:00:00+03',
       'open', 'Демонстрация транзакции'
FROM dining_tables AS t
CROSS JOIN staff AS s
WHERE t.table_number = 5 AND s.email = 'lab02.demo@restaurant.example'
RETURNING id, order_number, status;

INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price)
SELECT o.id, mi.id, 1, mi.price
FROM orders AS o
CROSS JOIN menu_items AS mi
JOIN menu_categories AS c ON c.id = mi.category_id
WHERE o.order_number = 'L2-DML-DEMO'
  AND ((c.name = 'Основные блюда' AND mi.name = 'Паста')
    OR (c.name = 'Напитки' AND mi.name = 'Чай'))
RETURNING order_id, menu_item_id, quantity, unit_price;

-- 2. Гость отменил существующий открытый заказ до добавления позиций.
-- Заказ пуст и не оплачен, поэтому возврат денег не требуется.
UPDATE orders SET status = 'cancelled'
WHERE order_number = 'L2-202608-06' AND status = 'open'
RETURNING order_number, status;

-- 3. Акция: скидка 10% на доступные десерты дороже 300 рублей.
-- Исторические цены в order_items эта операция не изменяет.
UPDATE menu_items AS mi
SET price = ROUND(mi.price * 0.90, 2)
FROM menu_categories AS c
WHERE mi.category_id = c.id AND c.name = 'Десерты'
  AND mi.is_available AND mi.price > 300.00
RETURNING mi.name, mi.price;

-- 4. Попытка удалить сотрудника с заказом отклоняется ON DELETE RESTRICT.
DO $$
BEGIN
    BEGIN
        DELETE FROM staff WHERE email = 'lab02.demo@restaurant.example';
        RAISE EXCEPTION 'Ожидался запрет удаления сотрудника с заказом';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'Удаление сотрудника с заказом отклонено внешним ключом';
    END;
END $$;

-- Корректный порядок: сначала дочерние строки, затем родительские.
DELETE FROM order_items
WHERE order_id = (SELECT id FROM orders WHERE order_number = 'L2-DML-DEMO')
RETURNING order_id, menu_item_id;
DELETE FROM orders WHERE order_number = 'L2-DML-DEMO'
RETURNING order_number;
DELETE FROM staff WHERE email = 'lab02.demo@restaurant.example'
RETURNING full_name;

-- 5. Отмена UPDATE и всех INSERT/DELETE в демонстрации.
ROLLBACK;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM lab02_dml_snapshot AS before
        WHERE before.staff_rows IS DISTINCT FROM
                  (SELECT jsonb_agg(to_jsonb(s) ORDER BY s.id) FROM staff AS s)
           OR before.menu_rows IS DISTINCT FROM
                  (SELECT jsonb_agg(to_jsonb(m) ORDER BY m.id) FROM menu_items AS m)
           OR before.order_rows IS DISTINCT FROM
                  (SELECT jsonb_agg(to_jsonb(o) ORDER BY o.id) FROM orders AS o)
           OR before.item_rows IS DISTINCT FROM
                  (SELECT jsonb_agg(to_jsonb(i) ORDER BY i.id) FROM order_items AS i)
    ) THEN
        RAISE EXCEPTION 'ROLLBACK не восстановил исходные строки';
    END IF;
    RAISE NOTICE 'ROLLBACK проверен: строки всех затронутых таблиц восстановлены';
END $$;
DROP TABLE lab02_dml_snapshot;

SELECT order_number, status FROM orders WHERE order_number = 'L2-202608-06';
SELECT mi.name, mi.price
FROM menu_items AS mi
JOIN menu_categories AS c ON c.id = mi.category_id
WHERE c.name = 'Десерты'
ORDER BY mi.name;
