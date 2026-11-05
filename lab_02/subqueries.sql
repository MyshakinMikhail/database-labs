SELECT c.name AS category, mi.name AS item, mi.price,
       ROUND((SELECT AVG(peer.price) FROM menu_items AS peer
              WHERE peer.category_id = mi.category_id), 2) AS category_average
FROM menu_items AS mi
JOIN menu_categories AS c ON c.id = mi.category_id
WHERE mi.price > (SELECT AVG(peer.price) FROM menu_items AS peer
                 WHERE peer.category_id = mi.category_id)
ORDER BY c.name, mi.price DESC, mi.name;

SELECT s.full_name, s.email
FROM staff AS s
WHERE EXISTS (
    SELECT 1
    FROM orders AS o
    JOIN payments AS p ON p.order_id = o.id
    WHERE o.staff_id = s.id AND o.status_code = 'closed' AND p.method = 'cash'
)
ORDER BY s.full_name;

SELECT o.order_number, s.full_name, t.total AS unpaid_amount
FROM orders AS o
JOIN staff AS s ON s.id = o.staff_id
JOIN (
    SELECT order_id, SUM(quantity * unit_price) AS total
    FROM order_items
    GROUP BY order_id
) AS t ON t.order_id = o.id
WHERE o.status_code = 'closed'
  AND NOT EXISTS (SELECT 1 FROM payments AS p WHERE p.order_id = o.id)
ORDER BY o.opened_at, o.order_number;

SELECT s.full_name,
       (SELECT ROUND(AVG(COALESCE(t.total, 0)), 2)
        FROM orders AS o
        LEFT JOIN (
            SELECT order_id, SUM(quantity * unit_price) AS total
            FROM order_items
            GROUP BY order_id
        ) AS t ON t.order_id = o.id
        WHERE o.staff_id = s.id AND o.status_code = 'closed') AS average_closed_check,
       (SELECT MAX(o.opened_at) FROM orders AS o
        WHERE o.staff_id = s.id) AS last_order_at
FROM staff AS s
ORDER BY s.full_name;
