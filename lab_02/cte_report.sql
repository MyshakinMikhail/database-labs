-- Часть 4. Какие сотрудники и в какие месяцы обеспечили продажи,
-- сколько получено по закрытым заказам и какая сумма осталась неоплаченной?
-- Месяц определяется датой открытия заказа в часовом поясе ресторана.
-- Оплаты относятся к месяцу заказа: это не отчёт о движении денег по paid_at.
WITH
-- Исходные данные -> промежуточные суммы: одна строка на заказ в каждом CTE.
item_totals AS (
    SELECT order_id, SUM(quantity * unit_price) AS order_total
    FROM order_items
    GROUP BY order_id
),
payment_totals AS (
    SELECT order_id, SUM(amount) AS paid_total
    FROM payments
    GROUP BY order_id
),
-- Два набора агрегируются ДО соединения: три позиции и два платежа
-- не превращаются в шесть строк с завышенными суммами.
order_metrics AS (
    SELECT o.id, o.staff_id, o.status,
           date_trunc('month', o.opened_at AT TIME ZONE 'Europe/Moscow')::DATE
               AS month,
           COALESCE(i.order_total, 0) AS order_total,
           COALESCE(p.paid_total, 0) AS paid_total,
           GREATEST(COALESCE(i.order_total, 0) - COALESCE(p.paid_total, 0), 0)
               AS outstanding
    FROM orders AS o
    LEFT JOIN item_totals AS i ON i.order_id = o.id
    LEFT JOIN payment_totals AS p ON p.order_id = o.id
),
-- Промежуточные показатели -> агрегация по месяцу и сотруднику.
monthly_summary AS (
    SELECT month, staff_id, COUNT(*) AS orders_count,
           COUNT(*) FILTER (WHERE status = 'closed') AS closed_count,
           COUNT(*) FILTER (WHERE status = 'open') AS open_count,
           COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_count,
           COALESCE(SUM(order_total) FILTER (WHERE status = 'closed'), 0)
               AS closed_sales,
           COALESCE(SUM(paid_total) FILTER (WHERE status = 'closed'), 0)
               AS collected,
           COALESCE(SUM(outstanding) FILTER (WHERE status = 'closed'), 0)
               AS closed_debt,
           COUNT(*) FILTER (WHERE status = 'closed' AND outstanding > 0)
               AS unpaid_closed_count,
           COALESCE(SUM(outstanding) FILTER (WHERE status = 'open'), 0)
               AS open_balance
    FROM order_metrics
    GROUP BY month, staff_id
),
-- Агрегация -> итог: сохраняем и сотрудников без единого заказа.
months AS (
    SELECT DISTINCT month FROM order_metrics
)
SELECT m.month, s.full_name,
       COALESCE(ms.orders_count, 0) AS orders_count,
       COALESCE(ms.closed_count, 0) AS closed_count,
       COALESCE(ms.open_count, 0) AS open_count,
       COALESCE(ms.cancelled_count, 0) AS cancelled_count,
       COALESCE(ms.closed_sales, 0) AS closed_sales,
       COALESCE(ms.collected, 0) AS collected,
       COALESCE(ms.closed_debt, 0) AS closed_debt,
       COALESCE(ms.unpaid_closed_count, 0) AS unpaid_closed_count,
       COALESCE(ms.open_balance, 0) AS open_balance,
       ROUND(100.0 * ms.collected / NULLIF(ms.closed_sales, 0), 2)
           AS collection_percent
FROM months AS m
CROSS JOIN staff AS s
LEFT JOIN monthly_summary AS ms ON ms.month = m.month AND ms.staff_id = s.id
ORDER BY m.month, s.full_name;
