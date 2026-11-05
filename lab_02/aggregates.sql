SELECT s.full_name, COUNT(o.id) AS orders_count,
       COUNT(o.id) FILTER (WHERE o.status_code = 'open') AS open_count,
       COUNT(o.id) FILTER (WHERE o.status_code = 'closed') AS closed_count,
       COUNT(o.id) FILTER (WHERE o.status_code = 'cancelled') AS cancelled_count
FROM staff AS s
LEFT JOIN orders AS o ON o.staff_id = s.id
GROUP BY s.id, s.full_name
ORDER BY orders_count DESC, s.full_name;

SELECT s.full_name, COUNT(o.id) AS closed_count,
       SUM(COALESCE(t.total, 0)) AS closed_sales,
       ROUND(AVG(COALESCE(t.total, 0)), 2) AS average_check,
       MIN(COALESCE(t.total, 0)) AS min_check,
       MAX(COALESCE(t.total, 0)) AS max_check
FROM staff AS s
JOIN orders AS o ON o.staff_id = s.id
LEFT JOIN (
    SELECT order_id, SUM(quantity * unit_price) AS total
    FROM order_items
    GROUP BY order_id
) AS t ON t.order_id = o.id
WHERE o.status_code = 'closed'
GROUP BY s.id, s.full_name
HAVING SUM(COALESCE(t.total, 0)) >= 10000.00
ORDER BY closed_sales DESC, s.full_name;

SELECT periods.month, c.name AS category,
       COUNT(DISTINCT o.id) AS orders_count,
       COALESCE(SUM(oi.quantity) FILTER (WHERE o.id IS NOT NULL), 0) AS portions,
       COALESCE(SUM(oi.quantity * oi.unit_price)
           FILTER (WHERE o.id IS NOT NULL), 0) AS sales
FROM menu_categories AS c
CROSS JOIN (
    SELECT DISTINCT date_trunc('month', opened_at AT TIME ZONE 'Europe/Moscow')::DATE
        AS month
    FROM orders
) AS periods
LEFT JOIN menu_items AS mi ON mi.category_id = c.id
LEFT JOIN order_items AS oi ON oi.menu_item_id = mi.id
LEFT JOIN orders AS o ON o.id = oi.order_id AND o.status_code = 'closed'
    AND (o.opened_at AT TIME ZONE 'Europe/Moscow')::DATE >= periods.month
    AND (o.opened_at AT TIME ZONE 'Europe/Moscow')::DATE
        < (periods.month + INTERVAL '1 month')::DATE
GROUP BY periods.month, c.id, c.name
ORDER BY periods.month, c.name;
