DO $$
BEGIN
    INSERT INTO dining_tables (table_number, seats) VALUES (1, 4);
    RAISE EXCEPTION 'Тест 1 не пройден: повтор номера столика принят';
EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'Тест 1 пройден: повтор номера столика отклонён';
END $$;

DO $$
BEGIN
    INSERT INTO menu_items (category_id, name, price)
    VALUES ((SELECT id FROM menu_categories WHERE name = 'Закуски'), 'Брускетта', 400.00);
    RAISE EXCEPTION 'Тест 2 не пройден: повтор блюда в категории принят';
EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'Тест 2 пройден: повтор блюда в категории отклонён';
END $$;

DO $$
BEGIN
    UPDATE menu_items SET price = -10.00 WHERE name = 'Кофе';
    RAISE EXCEPTION 'Тест 3 не пройден: отрицательная цена принята';
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'Тест 3 пройден: отрицательная цена отклонена';
END $$;

DO $$
BEGIN
    INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price)
    VALUES (
        (SELECT id FROM orders WHERE order_number = 'R-104'),
        (SELECT id FROM menu_items WHERE name = 'Лимонад'),
        0,
        300.00
    );
    RAISE EXCEPTION 'Тест 4 не пройден: нулевое количество принято';
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'Тест 4 пройден: нулевое количество отклонено';
END $$;

DO $$
BEGIN
    INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price)
    VALUES ((SELECT id FROM orders WHERE order_number = 'R-104'), -1, 1, 100.00);
    RAISE EXCEPTION 'Тест 5 не пройден: несуществующее блюдо принято';
EXCEPTION WHEN foreign_key_violation THEN
    RAISE NOTICE 'Тест 5 пройден: несуществующее блюдо отклонено';
END $$;

DO $$
BEGIN
    INSERT INTO staff (full_name, email, role)
    VALUES (NULL, 'invalid@restaurant.example', 'waiter');
    RAISE EXCEPTION 'Тест 6 не пройден: сотрудник без имени принят';
EXCEPTION WHEN not_null_violation THEN
    RAISE NOTICE 'Тест 6 пройден: сотрудник без имени отклонён';
END $$;

DO $$
BEGIN
    INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price)
    VALUES (
        (SELECT id FROM orders WHERE order_number = 'R-101'),
        (SELECT id FROM menu_items WHERE name = 'Брускетта'),
        1,
        350.00
    );
    RAISE EXCEPTION 'Тест 7 не пройден: повтор блюда в заказе принят';
EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'Тест 7 пройден: повтор блюда в заказе отклонён';
END $$;

DO $$
BEGIN
    INSERT INTO payments (order_id, amount, method)
    VALUES ((SELECT id FROM orders WHERE order_number = 'R-104'), 0.00, 'cash');
    RAISE EXCEPTION 'Тест 8 не пройден: нулевая оплата принята';
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'Тест 8 пройден: нулевая оплата отклонена';
END $$;
