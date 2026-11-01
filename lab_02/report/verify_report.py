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
TABLES = ('staff', 'dining_tables', 'menu_categories', 'menu_items',
          'orders', 'order_items', 'payments')
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
    temp = Path(tempfile.mkdtemp(prefix='lab02-report-'))
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
            return {name: query('SELECT * FROM %s ORDER BY id' % name) for name in TABLES}

        call('-f', str(ROOT / 'lab_01/schema.sql'), '-f', str(ROOT / 'lab_01/data.sql'))
        before = snapshot()
        stdout, stderr = call('-f', str(ROOT / 'lab_02/run_all.sql'))
        (OUT / 'run_all.txt').write_text(stdout + '\n' + stderr)
        after = snapshot()
        preserved = True
        for table in TABLES:
            indexed = {row['id']: row for row in after[table]}
            for old in before[table]:
                preserved = preserved and old['id'] in indexed
                preserved = preserved and all(indexed.get(old['id'], {}).get(k) == v
                                              for k, v in old.items())
        check('B01', 'Исходные строки и значения ЛР 1 сохранены', preserved,
              {'before': {t: len(before[t]) for t in TABLES},
               'after': {t: len(after[t]) for t in TABLES}})
        check('B02', 'ROLLBACK восстановил строки четырёх таблиц',
              'ROLLBACK проверен: строки всех затронутых таблиц восстановлены' in stderr,
              'Проверка JSONB-снимков встроена в dml.sql')
        check('B03', 'Удаление родителя с дочерними строками запрещено',
              'Удаление сотрудника с заказом отклонено внешним ключом' in stderr,
              'Перехвачен foreign_key_violation; выполнено удаление детей перед родителем')
        _, constraints = call('-f', str(ROOT / 'lab_01/constraints_test.sql'))
        check('B04', 'Восемь проверок ограничений ЛР 1 проходят после ЛР 2',
              sum('пройден:' in line for line in constraints.splitlines()) == 8,
              constraints.strip().splitlines())
        check('B05', 'Проверки ограничений не изменили строки', snapshot() == after,
              'Полное сравнение содержимого всех семи таблиц')

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
              sum(len(v) for v in after.values()) >= 100, sum(len(v) for v in after.values()))
        check('D02', 'Не менее 30 заказов', len(orders) >= 30, len(orders))
        check('D03', 'Три состояния процесса', len({o['status'] for o in orders}) >= 3,
              {s: sum(o['status'] == s for o in orders) for s in ['open', 'closed', 'cancelled']})
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
            if month(o) != '2026-10-01' or o['status'] == 'cancelled':
                continue
            for i in oi_by_order[o['id']]:
                mi = items[i['menu_item_id']]
                expected.append(dict(order_number=o['order_number'], opened_at=o['opened_at'],
                    status=o['status'], full_name=people[o['staff_id']]['full_name'],
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
            if (o['status'] == 'closed' and t['seats'] >= 4
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
            sums = [amount[o['id']] for o in own if o['status'] == 'closed']
            expected.append(dict(full_name=s['full_name'], orders_count=len(own),
                **{status + '_count': sum(o['status'] == status for o in own)
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
                pairs = [(o, i) for o in orders if month(o) == m and o['status'] == 'closed'
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
                    if any(o['staff_id'] == s['id'] and o['status'] == 'closed'
                        and any(p['method'] == 'cash' for p in pay_by_order[o['id']]) for o in orders)]
        check('Q32', '3.2: EXISTS с дополнительным условием',
              same_rows(queries['3.2']['rows'], expected), {'rows':len(expected)})
        expected = [dict(order_number=o['order_number'], full_name=people[o['staff_id']]['full_name'],
                         unpaid_amount=amount[o['id']]) for o in orders
                    if o['status'] == 'closed' and oi_by_order[o['id']] and not pay_by_order[o['id']]]
        check('Q33', '3.3: NOT EXISTS находит отсутствие оплат',
              same_rows(queries['3.3']['rows'], expected), {'rows':len(expected)})
        check('Q34', '3.4: индивидуальные показатели и NULL',
              same_rows(queries['3.4']['rows'], expected_personal), {'rows':len(expected_personal)})
        expected = []
        for m in months:
            for s in people.values():
                own = [o for o in orders if month(o) == m and o['staff_id'] == s['id']]
                closed = [o for o in own if o['status'] == 'closed']
                sales = sum((amount[o['id']] for o in closed),D(0))
                got = sum((paid[o['id']] for o in closed),D(0))
                expected.append(dict(month=m, full_name=s['full_name'], orders_count=len(own),
                    **{st+'_count':sum(o['status']==st for o in own) for st in ('open','closed','cancelled')},
                    closed_sales=sales, collected=got,
                    closed_debt=sum((max(amount[o['id']]-paid[o['id']],D(0)) for o in closed),D(0)),
                    unpaid_closed_count=sum(amount[o['id']] > paid[o['id']] for o in closed),
                    open_balance=sum((max(amount[o['id']]-paid[o['id']],D(0)) for o in own if o['status']=='open'),D(0)),
                    collection_percent=rounded(100*got/sales) if sales else None))
        check('Q4', '4: все показатели CTE-отчёта совпали с независимым расчётом',
              same_rows(queries['4']['rows'], expected), {'rows':len(expected), 'fields_per_row':12})
        call('-f', str(ROOT / 'lab_02/run_all.sql'))
        check('B06', 'Повторный полный запуск не создаёт дубли и не меняет строки',
              snapshot() == after, 'Сравнены все 202 строки семи таблиц; последовательности в сравнение не входят')
        version = call('-At', '-c', 'SELECT version()')[0].strip()
        files = [ROOT/'lab_01/schema.sql', ROOT/'lab_01/data.sql',
                 ROOT/'lab_01/constraints_test.sql'] + sorted((ROOT/'lab_02').glob('*.sql'))
        evidence = dict(checked_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                        postgres=version, before=before, after=after, checks=checks, queries=queries,
                        sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in files})
        (OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,default=str))
        lines = [version, 'Проверено: '+evidence['checked_at']] + [
            '%s | PASS | %s | %s' % (c['id'],c['title'],json.dumps(c['detail'],ensure_ascii=False,default=str))
            for c in checks]
        (OUT/'verification.txt').write_text('\n'.join(lines)+'\n')
        print('\n'.join(lines))
    finally:
        if started:
            subprocess.run(['pg_ctl','-D',str(data),'-m','fast','-w','stop'],
                           check=True,capture_output=True)
        shutil.rmtree(temp)


if __name__ == '__main__':
    main()
