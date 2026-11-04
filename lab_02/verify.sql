-- Проверка минимальных требований к данным и нетривиальных ситуаций.
DO $$
DECLARE
    total_rows BIGINT;
BEGIN
    SELECT (SELECT COUNT(*) FROM staff)
         + (SELECT COUNT(*) FROM dining_tables)
         + (SELECT COUNT(*) FROM menu_categories)
         + (SELECT COUNT(*) FROM menu_items)
         + (SELECT COUNT(*) FROM orders)
         + (SELECT COUNT(*) FROM order_items)
         + (SELECT COUNT(*) FROM payments)
    INTO total_rows;
    IF total_rows < 100 THEN
        RAISE EXCEPTION 'Недостаточно записей: % вместо 100', total_rows;
    END IF;
    IF (SELECT COUNT(*) FROM orders) < 30 THEN
        RAISE EXCEPTION 'В основной операционной таблице меньше 30 заказов';
    END IF;
    IF (SELECT COUNT(DISTINCT status_code) FROM orders) < 3 THEN
        RAISE EXCEPTION 'Меньше трёх состояний заказа';
    END IF;
    IF EXISTS (
        SELECT 1 FROM orders AS o
        WHERE NOT EXISTS (
            SELECT 1 FROM order_status_history AS h WHERE h.order_id = o.id
        )
    ) THEN
        RAISE EXCEPTION 'Есть заказ без начальной записи истории статусов';
    END IF;
    IF (SELECT COUNT(DISTINCT date_trunc('month', opened_at
            AT TIME ZONE 'Europe/Moscow')) FROM orders) < 3 THEN
        RAISE EXCEPTION 'Данные охватывают меньше трёх месяцев';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM orders GROUP BY staff_id HAVING COUNT(*) > 1) THEN
        RAISE EXCEPTION 'Нет повторных операций у одной сущности';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM staff AS s WHERE NOT EXISTS
            (SELECT 1 FROM orders AS o WHERE o.staff_id = s.id)) THEN
        RAISE EXCEPTION 'Нет сотрудника без заказов';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM menu_items AS mi WHERE NOT EXISTS
            (SELECT 1 FROM order_items AS oi WHERE oi.menu_item_id = mi.id)) THEN
        RAISE EXCEPTION 'Нет блюда без заказов';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM orders AS o WHERE NOT EXISTS
            (SELECT 1 FROM order_items AS oi WHERE oi.order_id = o.id)) THEN
        RAISE EXCEPTION 'Нет пустого заказа с нулевой суммой';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM orders WHERE guest_note IS NULL) THEN
        RAISE EXCEPTION 'Нет допустимого NULL';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM orders AS o WHERE o.status_code = 'closed'
            AND EXISTS (SELECT 1 FROM order_items AS oi WHERE oi.order_id = o.id)
            AND NOT EXISTS (SELECT 1 FROM payments AS p WHERE p.order_id = o.id)) THEN
        RAISE EXCEPTION 'Нет закрытого непустого заказа без оплаты';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM orders AS o
            WHERE (SELECT COUNT(*) FROM order_items AS oi WHERE oi.order_id = o.id) > 1
              AND (SELECT COUNT(*) FROM payments AS p WHERE p.order_id = o.id) > 1) THEN
        RAISE EXCEPTION 'Нет заказа с несколькими позициями и платежами';
    END IF;
    RAISE NOTICE 'Требования к данным выполнены. Всего строк: %', total_rows;
END $$;

SELECT 'staff' AS table_name, COUNT(*) AS row_count FROM staff
UNION ALL SELECT 'dining_tables', COUNT(*) FROM dining_tables
UNION ALL SELECT 'menu_categories', COUNT(*) FROM menu_categories
UNION ALL SELECT 'menu_items', COUNT(*) FROM menu_items
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'payments', COUNT(*) FROM payments
ORDER BY table_name;

SELECT date_trunc('month', opened_at AT TIME ZONE 'Europe/Moscow')::DATE AS month,
       COUNT(*) AS orders_count,
       COUNT(*) FILTER (WHERE status_code = 'closed') AS closed_count,
       COUNT(*) FILTER (WHERE status_code = 'open') AS open_count,
       COUNT(*) FILTER (WHERE status_code = 'cancelled') AS cancelled_count
FROM orders
GROUP BY month
ORDER BY month;
