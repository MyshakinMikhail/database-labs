\set ON_ERROR_STOP on
\pset pager off
\pset null 'NULL'
SET TIME ZONE 'Europe/Moscow';

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
