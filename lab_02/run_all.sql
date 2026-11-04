\set ON_ERROR_STOP on
\pset pager off
\pset null 'NULL'
SET TIME ZONE 'Europe/Moscow';

-- ЛР 2 продолжает окончательную модель ЛР 1; схему здесь не пересоздаём.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'orders'
          AND column_name = 'status_code'
    ) OR to_regclass('order_statuses') IS NULL
      OR to_regclass('order_status_history') IS NULL THEN
        RAISE EXCEPTION 'ЛР 2 требует завершённую ЛР 1: orders.status_code, справочник и историю статусов. Сначала примените lab_01/migration.sql к исходной схеме.';
    END IF;
END $$;

\echo '=== 1.1. Подготовка данных ==='
\ir prepare_data.sql
\echo '=== 1.2. INSERT, UPDATE, DELETE и ROLLBACK ==='
\ir dml.sql
\echo '=== 2.1. Три многотабличных запроса ==='
\ir joins.sql
\echo '=== 2.2. Три запроса с агрегацией ==='
\ir aggregates.sql
\echo '=== 3. Четыре запроса с подзапросами ==='
\ir subqueries.sql
\echo '=== 4. Комплексный отчёт с CTE ==='
\ir cte_report.sql
\echo '=== Проверка требований к данным ==='
\ir verify.sql
