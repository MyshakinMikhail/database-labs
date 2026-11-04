"""Воспроизводимая проверка ЛР 2 для иллюстрированного отчёта.

Требует PostgreSQL (initdb, pg_ctl, psql) в PATH. Создаёт временный кластер,
не подключается к существующим базам; останавливает и удаляет его в finally.
Запуск из любого каталога: python3 lab_02/report/verify_report.py
"""
import datetime as dt
from decimal import Decimal as D, ROUND_HALF_UP
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA_TABLES = ('staff', 'dining_tables', 'menu_categories', 'menu_items',
               'orders', 'order_items', 'payments')
TABLES = DATA_TABLES + ('order_statuses', 'order_status_history')


def row_key(table):
    return 'code' if table == 'order_statuses' else 'id'


checks = []


def check(key, title, condition, detail):
    if not condition:
        raise AssertionError(key + ': ' + title + ': ' + str(detail))
    checks.append(dict(id=key, title=title, status='PASS', detail=detail))


def statements(name):
    text = (ROOT / 'lab_02' / name).read_text()
    return [s.strip() for s in re.sub(r'^\s*--.*$', '', text, flags=re.M).split(';')
            if s.strip()]


def rounded(value):
    return value.quantize(D('0.01'), rounding=ROUND_HALF_UP)


def same_rows(actual, expected):
    return len(actual) == len(expected) and all(row in actual for row in expected)


def main():
    # Короткий путь нужен из-за ограничения длины Unix-сокета на macOS.
    temp = Path(tempfile.mkdtemp(prefix='lab02-report-', dir='/tmp'))
    data, sock = temp / 'pgdata', temp / 'socket'
    sock.mkdir()
    started = False
    try:
        subprocess.run(['initdb', '-D', str(data), '-U', 'lab_report', '-A', 'trust',
                        '--locale=C', '--encoding=UTF8'], check=True, capture_output=True)
        subprocess.run(['pg_ctl', '-D', str(data), '-l', str(temp / 'postgres.log'),
                        '-o', "-k %s -p 55433 -c listen_addresses=''" % sock,
                        '-w', 'start'], check=True, capture_output=True)
        started = True
        cmd = ['psql', '-X', '-w', '-h', str(sock), '-p', '55433', '-U', 'lab_report',
               '-d', 'postgres', '-v', 'ON_ERROR_STOP=1']

        def call(*args):
            p = subprocess.run(cmd + list(args), capture_output=True, text=True)
            if p.returncode:
                raise RuntimeError(p.stderr + p.stdout[-4000:])
            return p.stdout, p.stderr

        def query(sql):
            wrapped = "SELECT COALESCE(jsonb_agg(to_jsonb(q)), '[]'::jsonb) FROM (%s) AS q" % sql.rstrip(';')
            return json.loads(call('-At', '-c', wrapped)[0], parse_float=D)

        def snapshot():
            return {name: query('SELECT * FROM %s ORDER BY %s' % (name, row_key(name)))
                    for name in TABLES}

        call('-f', str(ROOT / 'lab_01/schema.sql'), '-f', str(ROOT / 'lab_01/data.sql'))
        original = {name: query('SELECT * FROM %s ORDER BY id' % name)
                    for name in DATA_TABLES}
        # Старую схему необходимо отклонять до первого изменения данных.
        rejected = subprocess.run(cmd + ['-f', str(ROOT / 'lab_02/run_all.sql')],
                                  capture_output=True, text=True)
        unchanged = all(query('SELECT * FROM %s ORDER BY id' % name) == original[name]
                        for name in DATA_TABLES)
        check('M01', 'ЛР 2 отклоняет немигрированную схему без изменения данных',
              rejected.returncode != 0 and 'ЛР 2 требует завершённую ЛР 1' in rejected.stderr
              and unchanged and not query("SELECT 1 FROM information_schema.columns "
                  "WHERE table_schema='public' AND table_name='orders' "
                  "AND column_name='guest_note'"),
              'Проверено до добавления guest_note и тестовых записей')
        call('-f', str(ROOT / 'lab_01/migration.sql'))
        before = snapshot()
        migrated = {name: [dict(row) for row in rows] for name, rows in original.items()}
        for row in migrated['orders']:
            row['status_code'] = row.pop('status')
        check('M02', 'Миграция сохранила все исходные строки и значения статусов',
              all(before[name] == migrated[name] for name in DATA_TABLES),
              'Единственное изменение исходных полей: status -> status_code')
        check('M03', 'Справочник и начальная история соответствуют заказам ЛР 1',
              {r['code'] for r in before['order_statuses']} == {'open', 'closed', 'cancelled'}
              and len(before['order_status_history']) == len(before['orders'])
              and all(any(h['order_id'] == o['id'] and h['status_code'] == o['status_code']
                          and h['is_backfilled'] for h in before['order_status_history'])
                      for o in before['orders']),
              {'statuses': len(before['order_statuses']),
               'backfilled': len(before['order_status_history'])})
        _, history_checks = call('-c', """
            BEGIN;
            DO $$
            DECLARE
                demo_id INT;
            BEGIN
                INSERT INTO orders (order_number, table_id, staff_id, status_code)
                VALUES ('L2-VERIFY-HISTORY', (SELECT MIN(id) FROM dining_tables),
                        (SELECT MIN(id) FROM staff), 'open') RETURNING id INTO demo_id;
                IF (SELECT COUNT(*) FROM order_status_history WHERE order_id = demo_id
                    AND status_code = 'open' AND NOT is_backfilled) <> 1 THEN
                    RAISE EXCEPTION 'Нет начального статуса нового заказа';
                END IF;
                UPDATE orders SET status_code = 'open' WHERE id = demo_id;
                IF (SELECT COUNT(*) FROM order_status_history WHERE order_id = demo_id) <> 1 THEN
                    RAISE EXCEPTION 'Повтор того же статуса создал лишнюю историю';
                END IF;
                UPDATE orders SET status_code = 'closed' WHERE id = demo_id;
                IF (SELECT COUNT(*) FROM order_status_history WHERE order_id = demo_id) <> 2
                   OR (SELECT COUNT(*) FROM order_status_history WHERE order_id = demo_id
                       AND status_code = 'closed' AND NOT is_backfilled) <> 1 THEN
                    RAISE EXCEPTION 'Смена статуса не зарегистрирована';
                END IF;
                RAISE NOTICE 'История: INSERT, смена и повтор статуса проверены';
                BEGIN
                    UPDATE orders SET status_code = 'invalid-status' WHERE id = demo_id;
                    RAISE EXCEPTION 'Неизвестный статус принят';
                EXCEPTION WHEN foreign_key_violation THEN
                    RAISE NOTICE 'Неизвестный статус отклонён';
                END;
                BEGIN
                    DELETE FROM orders WHERE id = demo_id;
                    RAISE EXCEPTION 'Удалён заказ с историей';
                EXCEPTION WHEN foreign_key_violation THEN
                    RAISE NOTICE 'История защищает заказ от удаления';
                END;
            END $$;
            ROLLBACK;
        """)
        check('M04', 'Триггер сохраняет начальный и новый статус без дублей',
              'История: INSERT, смена и повтор статуса проверены' in history_checks,
              'Количество событий: 1 после INSERT, 1 после повтора, 2 после смены')
        check('M05', 'Внешние ключи защищают код статуса и историю заказа',
              'Неизвестный статус отклонён' in history_checks
              and 'История защищает заказ от удаления' in history_checks,
              'Обе недопустимые операции отклонены foreign_key_violation')
        check('M06', 'ROLLBACK откатил тестовые заказы и события истории',
              snapshot() == before, 'Полное сравнение девяти таблиц')
        stdout, stderr = call('-f', str(ROOT / 'lab_02/run_all.sql'))
        run_output = '\n'.join(line.rstrip() for line in
                               (stdout + '\n' + stderr).splitlines()) + '\n'
        after = snapshot()
        preserved = True
        for table in TABLES:
            key = row_key(table)
            indexed = {row[key]: row for row in after[table]}
            for old in before[table]:
                preserved = preserved and old[key] in indexed
                preserved = preserved and all(indexed.get(old[key], {}).get(k) == v
                                              for k, v in old.items())
        check('B01', 'Исходные строки и значения ЛР 1 сохранены', preserved,
              {'before': {t: len(before[t]) for t in TABLES},
               'after': {t: len(after[t]) for t in TABLES}})
        check('B02', 'ROLLBACK восстановил строки пяти таблиц, включая историю',
              'ROLLBACK проверен: строки всех затронутых таблиц восстановлены' in stderr,
              'Проверка JSONB-снимков встроена в dml.sql')
        check('B03', 'Удаление родителя с дочерними строками запрещено',
              'Удаление сотрудника с заказом отклонено внешним ключом' in stderr
              and 'Удаление заказа с историей отклонено внешним ключом' in stderr,
              'Проверены связи сотрудника и истории; дочерние строки удалены первыми')
        _, constraints = call('-f', str(ROOT / 'lab_01/constraints_test.sql'))
        check('B04', 'Восемь проверок ограничений ЛР 1 проходят после ЛР 2',
              sum('пройден:' in line for line in constraints.splitlines()) == 8,
              constraints.strip().splitlines())
        check('B05', 'Проверки ограничений не изменили строки', snapshot() == after,
              'Полное сравнение содержимого всех девяти таблиц')

        orders = after['orders']
        oi_by_order = defaultdict(list)
        pay_by_order = defaultdict(list)
        for row in after['order_items']:
            oi_by_order[row['order_id']].append(row)
        for row in after['payments']:
            pay_by_order[row['order_id']].append(row)
        amount = {o['id']: sum((D(i['unit_price']) * i['quantity']
                               for i in oi_by_order[o['id']]), D(0)) for o in orders}
        paid = {o['id']: sum((D(p['amount']) for p in pay_by_order[o['id']]), D(0))
                for o in orders}
        people = {s['id']: s for s in after['staff']}
        tables = {t['id']: t for t in after['dining_tables']}
        items = {i['id']: i for i in after['menu_items']}
        cats = {c['id']: c for c in after['menu_categories']}
        month = lambda o: dt.datetime.fromisoformat(o['opened_at']).astimezone(
            dt.timezone(dt.timedelta(hours=3))).date().replace(day=1).isoformat()
        months = sorted({month(o) for o in orders})
        check('D01', 'Не менее 100 содержательных записей',
              sum(len(after[t]) for t in DATA_TABLES) >= 100,
              sum(len(after[t]) for t in DATA_TABLES))
        check('D02', 'Не менее 30 заказов', len(orders) >= 30, len(orders))
        check('D03', 'Три состояния процесса', len({o['status_code'] for o in orders}) >= 3,
              {s: sum(o['status_code'] == s for o in orders) for s in ['open', 'closed', 'cancelled']})
        check('D04', 'Три календарных месяца', len(months) >= 3, months)
        check('D05', 'Повторные операции одной сущности',
              any(sum(o['staff_id'] == s for o in orders) > 1 for s in people),
              {s['full_name']: sum(o['staff_id'] == s['id'] for o in orders)
               for s in people.values()})
        empty_staff = [s['full_name'] for s in people.values()
                       if not any(o['staff_id'] == s['id'] for o in orders)]
        check('D06', 'Сущность без связанных операций', bool(empty_staff), empty_staff)
        empty_orders = [o['order_number'] for o in orders if not oi_by_order[o['id']]]
        null_notes = sum(o['guest_note'] is None for o in orders)
        check('D07', 'Нулевые показатели и допустимый NULL', bool(empty_orders) and null_notes > 0,
              {'empty_orders': empty_orders, 'null_notes': null_notes,
               'seats_min': min(t['seats'] for t in tables.values()),
               'seats_max': max(t['seats'] for t in tables.values())})

        queries = {}
        for name, ids in [('joins.sql', ['2.1.1','2.1.2','2.1.3']),
                          ('aggregates.sql', ['2.2.1','2.2.2','2.2.3']),
                          ('subqueries.sql', ['3.1','3.2','3.3','3.4']),
                          ('cte_report.sql', ['4'])]:
            sqls = statements(name)
            assert len(sqls) == len(ids)
            for key, sql in zip(ids, sqls):
                queries[key] = dict(file=name, sql=sql, rows=query(sql))

        expected = []
        for o in orders:
            if month(o) != '2026-10-01' or o['status_code'] == 'cancelled':
                continue
            for i in oi_by_order[o['id']]:
                mi = items[i['menu_item_id']]
                expected.append(dict(order_number=o['order_number'], opened_at=o['opened_at'],
                    status_code=o['status_code'], full_name=people[o['staff_id']]['full_name'],
                    table_number=tables[o['table_id']]['table_number'],
                    category=cats[mi['category_id']]['name'], item=mi['name'],
                    quantity=i['quantity'], unit_price=D(i['unit_price']),
                    line_total=D(i['unit_price']) * i['quantity']))
        check('Q211', '2.1.1: детализация соответствует исходным позициям',
              same_rows(queries['2.1.1']['rows'], expected), {'rows': len(expected)})
        expected = [dict(category=cats[i['category_id']]['name'], item=i['name'],
                         price=i['price'], is_available=i['is_available'], ordered_portions=0)
                    for i in items.values() if not any(x['menu_item_id'] == i['id']
                    for x in after['order_items'])]
        check('Q212', '2.1.2: блюда без заказов найдены точно',
              same_rows(queries['2.1.2']['rows'], expected), {'items': [r['item'] for r in expected]})
        expected = []
        for o in orders:
            t = tables[o['table_id']]
            if (o['status_code'] == 'closed' and t['seats'] >= 4
                    and any(cats[items[i['menu_item_id']]['category_id']]['name'] == 'Основные блюда'
                            for i in oi_by_order[o['id']])
                    and any(p['method'] == 'card' for p in pay_by_order[o['id']])):
                expected.append(dict(order_number=o['order_number'], opened_at=o['opened_at'],
                    full_name=people[o['staff_id']]['full_name'], table_number=t['table_number'], seats=t['seats']))
        check('Q213', '2.1.3: совместные условия и уникальность заказов',
              same_rows(queries['2.1.3']['rows'], expected), {'rows': len(expected)})
        expected = []
        expected_checks = []
        expected_personal = []
        for s in people.values():
            own = [o for o in orders if o['staff_id'] == s['id']]
            sums = [amount[o['id']] for o in own if o['status_code'] == 'closed']
            expected.append(dict(full_name=s['full_name'], orders_count=len(own),
                **{status + '_count': sum(o['status_code'] == status for o in own)
                   for status in ('open','closed','cancelled')}))
            if sum(sums) >= 10000:
                expected_checks.append(dict(full_name=s['full_name'], closed_count=len(sums),
                    closed_sales=sum(sums), average_check=rounded(sum(sums)/len(sums)),
                    min_check=min(sums), max_check=max(sums)))
            expected_personal.append(dict(full_name=s['full_name'],
                average_closed_check=rounded(sum(sums)/len(sums)) if sums else None,
                last_order_at=max((o['opened_at'] for o in own), default=None)))
        check('Q221', '2.2.1: нагрузка и нулевые группы',
              same_rows(queries['2.2.1']['rows'], expected), {'rows':len(expected)})
        check('Q222', '2.2.2: все пять агрегатов и HAVING',
              same_rows(queries['2.2.2']['rows'], expected_checks), {'rows':len(expected_checks)})
        expected = []
        for m in months:
            for c in cats.values():
                pairs = [(o, i) for o in orders if month(o) == m and o['status_code'] == 'closed'
                         for i in oi_by_order[o['id']]
                         if items[i['menu_item_id']]['category_id'] == c['id']]
                expected.append(dict(month=m, category=c['name'],
                    orders_count=len({o['id'] for o, _ in pairs}),
                    portions=sum(i['quantity'] for _,i in pairs),
                    sales=sum((i['quantity']*D(i['unit_price']) for _,i in pairs),D(0))))
        check('Q223', '2.2.3: категории по месяцам, включая нулевые продажи',
              same_rows(queries['2.2.3']['rows'], expected), {'rows':len(expected)})
        expected = []
        for i in items.values():
            peers = [D(p['price']) for p in items.values() if p['category_id'] == i['category_id']]
            avg = sum(peers)/len(peers)
            if D(i['price']) > avg:
                expected.append(dict(category=cats[i['category_id']]['name'], item=i['name'],
                                     price=i['price'], category_average=rounded(avg)))
        check('Q31', '3.1: сравнение со средним своей категории',
              same_rows(queries['3.1']['rows'], expected), {'rows':len(expected)})
        expected = [dict(full_name=s['full_name'], email=s['email']) for s in people.values()
                    if any(o['staff_id'] == s['id'] and o['status_code'] == 'closed'
                        and any(p['method'] == 'cash' for p in pay_by_order[o['id']]) for o in orders)]
        check('Q32', '3.2: EXISTS с дополнительным условием',
              same_rows(queries['3.2']['rows'], expected), {'rows':len(expected)})
        expected = [dict(order_number=o['order_number'], full_name=people[o['staff_id']]['full_name'],
                         unpaid_amount=amount[o['id']]) for o in orders
                    if o['status_code'] == 'closed' and oi_by_order[o['id']] and not pay_by_order[o['id']]]
        check('Q33', '3.3: NOT EXISTS находит отсутствие оплат',
              same_rows(queries['3.3']['rows'], expected), {'rows':len(expected)})
        check('Q34', '3.4: индивидуальные показатели и NULL',
              same_rows(queries['3.4']['rows'], expected_personal), {'rows':len(expected_personal)})
        expected = []
        for m in months:
            for s in people.values():
                own = [o for o in orders if month(o) == m and o['staff_id'] == s['id']]
                closed = [o for o in own if o['status_code'] == 'closed']
                sales = sum((amount[o['id']] for o in closed),D(0))
                got = sum((paid[o['id']] for o in closed),D(0))
                expected.append(dict(month=m, full_name=s['full_name'], orders_count=len(own),
                    **{st+'_count':sum(o['status_code']==st for o in own) for st in ('open','closed','cancelled')},
                    closed_sales=sales, collected=got,
                    closed_debt=sum((max(amount[o['id']]-paid[o['id']],D(0)) for o in closed),D(0)),
                    unpaid_closed_count=sum(amount[o['id']] > paid[o['id']] for o in closed),
                    open_balance=sum((max(amount[o['id']]-paid[o['id']],D(0)) for o in own if o['status_code']=='open'),D(0)),
                    collection_percent=rounded(100*got/sales) if sales else None))
        check('Q4', '4: все показатели CTE-отчёта совпали с независимым расчётом',
              same_rows(queries['4']['rows'], expected), {'rows':len(expected), 'fields_per_row':12})
        call('-f', str(ROOT / 'lab_02/run_all.sql'))
        check('B06', 'Повторный полный запуск не создаёт дубли и не меняет строки',
              snapshot() == after,
              'Сравнены девять таблиц, включая справочник и историю; последовательности не сравниваются')
        version = call('-At', '-c', 'SELECT version()')[0].strip()
        files = [ROOT/'lab_01/schema.sql', ROOT/'lab_01/data.sql',
                 ROOT/'lab_01/constraints_test.sql', ROOT/'lab_01/migration.sql'] + sorted((ROOT/'lab_02').glob('*.sql'))
        evidence = dict(checked_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                        postgres=version, before=before, after=after, checks=checks, queries=queries,
                        data_tables=DATA_TABLES,
                        sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in files})
        (OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,default=str))
        lines = [version, 'Проверено: '+evidence['checked_at']] + [
            '%s | PASS | %s | %s' % (c['id'],c['title'],json.dumps(c['detail'],ensure_ascii=False,default=str))
            for c in checks]
        (OUT/'verification.txt').write_text('\n'.join(lines)+'\n')
        (OUT/'run_all.txt').write_text(run_output)
        (ROOT/'lab_02/results.txt').write_text(run_output)
        print('\n'.join(lines))
    finally:
        if started:
            subprocess.run(['pg_ctl','-D',str(data),'-m','fast','-w','stop'],
                           check=True,capture_output=True)
        shutil.rmtree(temp)


if __name__ == '__main__':
    main()
