-- 2.1.1. Подробный состав неотменённых заказов за октябрь 2026 года:
-- заказ, сотрудник, столик, блюдо, категория, количество и стоимость.
-- Шесть таблиц; одна строка результата соответствует позиции заказа.
SELECT o.order_number, o.opened_at, o.status, s.full_name,
       t.table_number, c.name AS category, mi.name AS item,
       oi.quantity, oi.unit_price, oi.quantity * oi.unit_price AS line_total
FROM orders AS o
JOIN staff AS s ON s.id = o.staff_id
JOIN dining_tables AS t ON t.id = o.table_id
JOIN order_items AS oi ON oi.order_id = o.id
JOIN menu_items AS mi ON mi.id = oi.menu_item_id
JOIN menu_categories AS c ON c.id = mi.category_id
WHERE o.opened_at >= TIMESTAMPTZ '2026-10-01 00:00:00+03'
  AND o.opened_at < TIMESTAMPTZ '2026-11-01 00:00:00+03'
  AND o.status <> 'cancelled'
ORDER BY o.opened_at, o.order_number, c.name, mi.name;

-- 2.1.2. Блюда, которые ни разу не включали в заказ.
-- Три таблицы; LEFT JOIN сохраняет блюдо без позиций заказа.
-- Проверяется ключ дочерней строки, а не nullable бизнес-атрибут.
SELECT c.name AS category, mi.name AS item, mi.price, mi.is_available,
       COALESCE(oi.quantity, 0) AS ordered_portions
FROM menu_items AS mi
JOIN menu_categories AS c ON c.id = mi.category_id
LEFT JOIN order_items AS oi ON oi.menu_item_id = mi.id
WHERE oi.id IS NULL
ORDER BY c.name, mi.name;

-- 2.1.3. Закрытые заказы за столиками от четырёх мест, содержащие
-- основное блюдо и хотя бы один платёж картой.
-- DISTINCT нужен, поскольку в заказе может быть несколько подходящих
-- позиций и несколько платежей; результат содержит одну строку на заказ.
SELECT DISTINCT o.order_number, o.opened_at, s.full_name,
       t.table_number, t.seats
FROM orders AS o
JOIN dining_tables AS t ON t.id = o.table_id
JOIN staff AS s ON s.id = o.staff_id
JOIN order_items AS oi ON oi.order_id = o.id
JOIN menu_items AS mi ON mi.id = oi.menu_item_id
JOIN menu_categories AS c ON c.id = mi.category_id
JOIN payments AS p ON p.order_id = o.id
WHERE o.status = 'closed' AND t.seats >= 4
  AND c.name = 'Основные блюда' AND p.method = 'card'
ORDER BY o.opened_at, o.order_number;
