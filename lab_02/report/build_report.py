"""Сборка иллюстрированного PDF из кода ЛР 2 и результатов verify_report.py."""
from pathlib import Path
from decimal import Decimal
import json
import math
import re
from xml.sax.saxutils import escape

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE/'evidence.json').read_text())
PDF = ROOT/'output/pdf/lab_02_explained.pdf'
PDF.parent.mkdir(parents=True, exist_ok=True)
QA = ROOT/'tmp/pdfs'
QA.mkdir(parents=True, exist_ok=True)

for name, path in [
    ('Body','/System/Library/Fonts/Supplemental/Arial.ttf'),
    ('Bold','/System/Library/Fonts/Supplemental/Arial Bold.ttf'),
    ('Italic','/System/Library/Fonts/Supplemental/Arial Italic.ttf'),
    ('Mono','/System/Library/Fonts/Menlo.ttc')]:
    pdfmetrics.registerFont(TTFont(name,path))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Italic',boldItalic='Bold')

PW, PH = A4
M = 42
W = PW-2*M
NAVY = colors.HexColor('#17324D')
BLUE = colors.HexColor('#2468A0')
TEAL = colors.HexColor('#087F8C')
GREEN = colors.HexColor('#198465')
AMBER = colors.HexColor('#AF6800')
RED = colors.HexColor('#B94740')
GRAY = colors.HexColor('#586979')
LIGHT = colors.HexColor('#EFF4F8')
LINE = colors.HexColor('#D7E2EA')
C = canvas.Canvas(str(PDF),pagesize=A4,pageCompression=1)
C.setTitle('Лабораторная работа № 2: подробный разбор и проверка реализации')
C.setAuthor('Учебный проект database_labs')
C.setSubject('Вариант 14. Ресторан. Связь с ЛР 1, SQL, иллюстрации и проверка корректности')
page_no = 0
y = 0
pages = []


def clean(s):
    return str(s).replace('\u2011','-').replace('\u2013','-').replace('\u2014','-').replace('\u2212','-')


def p_at(text,x,top,width,size=10,leading=None,color=NAVY,bold=False):
    sty = ParagraphStyle('p',fontName='Bold' if bold else 'Body',fontSize=size,
        leading=leading or size*1.4,textColor=color,spaceAfter=0)
    obj = Paragraph(clean(text),sty)
    _, h = obj.wrap(width,1000)
    obj.drawOn(C,x,top-h)
    return h


def para(text,size=10,gap=8,color=NAVY):
    global y
    h=p_at(text,M,y,W,size,color=color)
    y-=h+gap


def heading(text):
    global y
    y-=5
    h=p_at(text,M,y,W,12,16,color=BLUE,bold=True)
    y-=h+7


def small(text):
    para(text,8.3,6,GRAY)


def callout(title,text,tint=LIGHT,accent=TEAL):
    global y
    st=ParagraphStyle('call',fontName='Body',fontSize=10,leading=14,textColor=NAVY)
    a=Paragraph('<b>'+clean(title)+'</b><br/>'+clean(text),st)
    _,h=a.wrap(W-28,1000)
    h+=22
    C.setFillColor(tint); C.roundRect(M,y-h,W,h,6,fill=1,stroke=0)
    C.setFillColor(accent); C.rect(M,y-h,3,h,fill=1,stroke=0)
    a.drawOn(C,M+14,y-h+11)
    y-=h+12


def table(headers,rows,widths=None,size=9):
    global y
    if widths is None:
        widths=[W/len(headers)]*len(headers)
    elif abs(sum(widths)-1)<0.01:
        widths=[v*W for v in widths]
    normal=ParagraphStyle('cell',fontName='Body',fontSize=size,leading=size*1.3,textColor=NAVY)
    header=ParagraphStyle('head',parent=normal,fontName='Bold',textColor=colors.white)
    def cell(t,sty):
        return Paragraph(escape(clean(t)).replace('\n','<br/>'),sty)
    dat=[[cell(v,header) for v in headers]]+[[cell(v,normal) for v in row] for row in rows]
    t=Table(dat,colWidths=widths,hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),NAVY),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LINEBELOW',(0,-1),(-1,-1),0.5,LINE)]))
    _,h=t.wrap(W,1000)
    t.drawOn(C,M,y-h)
    y-=h+11


def code(text,size=7.6):
    global y
    lines=clean(text).strip().splitlines()
    maxw=max(pdfmetrics.stringWidth(line,'Mono',size) for line in lines)
    if maxw>W-26:
        size*= (W-26)/maxw
    assert size>=6.7,(page_no,'Code too small',size)
    leading=size*1.38
    h=len(lines)*leading+20
    C.setFillColor(colors.HexColor('#F3F6F9')); C.roundRect(M,y-h,W,h,5,fill=1,stroke=0)
    C.setFont('Mono',size)
    for i,line in enumerate(lines):
        C.setFillColor(BLUE if re.match(r'\s*(SELECT|FROM|WHERE|JOIN|LEFT JOIN|WITH|GROUP BY|HAVING|ORDER BY|UPDATE|INSERT|DELETE|ROLLBACK)',line) else NAVY)
        C.drawString(M+12,y-13-i*leading,line)
    y-=h+10


def money(v):
    return f'{Decimal(str(v)):,.2f}'.replace(',',' ').replace('.',',')


def value(v):
    if v is None: return 'NULL'
    if isinstance(v,bool): return 'TRUE' if v else 'FALSE'
    return str(v)


def result(key,columns,labels,limit=None,widths=None,size=9):
    rows=DATA['queries'][key]['rows']
    table(labels,[[value(r.get(k)) for k in columns] for r in rows[:limit]],widths,size)
    small('Фактический результат: %s строк. Источник: lab_02/%s; проверка %s.' %
          (len(rows),DATA['queries'][key]['file'],'Q'+key.replace('.','')))


def query_code(key):
    code(DATA['queries'][key]['sql']+';')


def figure(h,fn,caption):
    global y
    C.saveState(); C.translate(M,y-h); fn(W,h); C.restoreState()
    y-=h+7
    small(caption)


def text(x,yy,s,size=10,color=NAVY,font='Body'):
    C.setFillColor(color); C.setFont(font,size); C.drawString(x,yy,clean(s))


def box(x,yy,w,h,title,sub='',fill=LIGHT,color=BLUE):
    C.setFillColor(fill); C.setStrokeColor(LINE); C.roundRect(x,yy,w,h,6,fill=1,stroke=1)
    p_at(title,x+10,yy+h-10,w-20,10.5,14,color,bold=True)
    if sub: p_at(sub,x+10,yy+h-31,w-20,9.3,12,NAVY)


def arrow(x1,y1,x2,y2,color=BLUE):
    C.setStrokeColor(color); C.setLineWidth(1.4); C.line(x1,y1,x2,y2)
    angle=math.atan2(y2-y1,x2-x1)
    p=C.beginPath(); p.moveTo(x2,y2)
    p.lineTo(x2-6*math.cos(angle-.45),y2-6*math.sin(angle-.45))
    p.lineTo(x2-6*math.cos(angle+.45),y2-6*math.sin(angle+.45));p.close()
    C.setFillColor(color);C.drawPath(p,fill=1,stroke=0)


def begin(title,kicker='ПОДРОБНЫЙ РАЗБОР ЛР 2',subtitle=None):
    global page_no,y
    page_no+=1
    C.setFillColor(TEAL);C.rect(0,PH-7,PW,7,fill=1,stroke=0)
    text(M,PH-31,kicker,8,GRAY,'Bold')
    text(PW-M-81,PH-31,'ВАРИАНТ 14',8,GRAY,'Bold')
    y=PH-53
    h=p_at(title,M,y,W,21,25,NAVY,bold=True);y-=h+14
    if subtitle: para(subtitle,10.4,12,GRAY)
    C.bookmarkPage('page'+str(page_no))
    C.addOutlineEntry(clean(title),'page'+str(page_no),level=0,closed=False)
    pages.append({'page':page_no,'title':title})


def end():
    assert y>=53,('Page overflow',page_no,pages[-1]['title'],y)
    pages[-1]['bottom']=round(y,1)
    C.setStrokeColor(LINE);C.setLineWidth(.6);C.line(M,40,PW-M,40)
    text(M,26,'Ресторан / ЛР 1 -> ЛР 2 / PostgreSQL 17.11',8,GRAY)
    C.setFont('Body',8);C.setFillColor(GRAY);C.drawRightString(PW-M,26,str(page_no))
    C.showPage()


def cover_flow(w,h):
    bw=(w-36)/2
    box(0,40,bw,114,'ЛАБОРАТОРНАЯ 1','Структура и ограничения<br/>7 таблиц, 42 строки<br/>5 исходных заказов')
    box(bw+36,40,bw,114,'ЛАБОРАТОРНАЯ 2','Те же связи + новые данные<br/>202 строки, 41 заказ<br/>11 запросов и аналитика',fill=colors.HexColor('#E7F5F1'),color=TEAL)
    arrow(bw+5,96,bw+31,96)
    text(5,15,'Схема сохранена. Расширение: orders.guest_note TEXT NULL.',10,GRAY)


begin('Лабораторная работа № 2',subtitle='Разработка SQL-запросов и аналитических сценариев для реляционной базы данных')
para('<b>Подробное объяснение реализации, связь с первой лабораторной и поэтапная проверка корректности.</b>',12,18)
figure(176,cover_flow,'Рисунок 1. ЛР 2 продолжает исходную модель ресторана, используя её таблицы и ограничения.')
table(['Показатель','Подтверждённое значение'],[
    ['Предметная область','Ресторан, вариант 14'],
    ['Объём данных','202 записи; 41 заказ; 3 календарных месяца'],
    ['SQL-запросы','3 JOIN + 3 GROUP BY + 4 подзапроса + 1 CTE-отчёт'],
    ['Проверка реализации','24 проверки PASS, в том числе независимая сверка всех запросов'],
    ['Ограничения ЛР 1','Все 8 исходных проверок проходят после расширения базы']],[.32,.68],10)
callout('Что считается доказательством','В документе приведены SQL из файлов проекта, фактические результаты PostgreSQL и ручные расчёты контрольных примеров. Дополнительно все результаты сверены отдельным Python-расчётом по строкам таблиц.')
small('Дата проверки: 22.10.2026. Источники: lab_01/schema.sql, lab_01/data.sql, lab_02/*.sql, lab_02/report/evidence.json.')
end()

begin('Как устроен этот разбор')
para('Документ можно читать последовательно или использовать как пояснение на защите. Для каждого задания указаны смысл, устройство SQL, фактический результат и причина, по которой результат соответствует требованию.')
table(['Страницы','Содержание'],[
    ['3-4','Связь с ЛР 1: ER-диаграмма, ключи, типы, нормализация, границы совместимости'],
    ['5-6','Набор данных: объём, три месяца, состояния и пограничные ситуации'],
    ['7-8','DML: вставка, обновление, массовое изменение, удаление и откат'],
    ['9-11','Три многотабличных запроса с JOIN'],
    ['12-15','Три аналитических запроса с GROUP BY и разбор их результатов'],
    ['16-19','Среднее по группе, EXISTS, NOT EXISTS и коррелированные подзапросы'],
    ['20-24','CTE-отчёт: этапы, защита от удвоения, полный SQL и итоговые суммы'],
    ['25-27','Метод проверки, матрица требований и подтверждения по пунктам'],
    ['28','Воспроизведение и вопросы, которые могут возникнуть на защите']],[.16,.84],10)
heading('Как связаны пояснение и проверка')
para('<b>Логическое объяснение</b> показывает, почему условие и соединения выражают нужный вопрос. <b>Пример</b> позволяет пересчитать конкретную сумму вручную. <b>Автоматическая проверка</b> сравнивает весь результат SQL с отдельным расчётом на Python.')
callout('Граница подтверждения','Доказательства относятся к текущим файлам проекта и указанному тестовому набору. Это проверка учебной реализации и её результатов, включая крайние случаи, присутствующие в данных; она не заменяет описание всех возможных бизнес-правил ресторана.')
small('Машинные доказательства: report/verification.txt и report/evidence.json. Воспроизводимый проверяющий сценарий: report/verify_report.py.')
end()

begin('1. Связь с первой лабораторной',subtitle='Те же семь сущностей и те же внешние ключи')
img=Image.open(ROOT/'lab_01/er_diagram.png')
ih=W*img.height/img.width
C.drawImage(str(ROOT/'lab_01/er_diagram.png'),M,y-ih,width=W,height=ih)
y-=ih+9
small('Рисунок 2. Исходная ER-диаграмма из lab_01/er_diagram.png. Обозначение 1 : 0..N допускает отсутствие дочерних строк.')
table(['Связь','Что она означает в работе'],[
    ['staff -> orders','Официант ведёт несколько заказов. Позволяет считать нагрузку и средний чек.'],
    ['dining_tables -> orders','Столик используется многократно. Позволяет отбирать заказы по вместимости.'],
    ['menu_categories -> menu_items','Блюдо относится к категории. Нужна для сравнения цен и продаж.'],
    ['orders -> order_items <- menu_items','Позиция связывает заказ с блюдом и хранит количество и цену продажи.'],
    ['orders -> payments','Заказ имеет 0, 1 или несколько оплат. Позволяет находить отсутствие оплаты и долг.']],[.39,.61],9.4)
para('Все запросы ЛР 2 строятся по этим связям. Отдельная упрощённая схема или демонстрационная база не используется.')
end()

begin('Что сохранено и что добавлено')
table(['Решение из ЛР 1','Значение для ЛР 2'],[
    ['INT GENERATED ALWAYS AS IDENTITY','Ключи генерируются PostgreSQL; ссылки ищутся по уникальным номерам, email и названиям.'],
    ['PRIMARY KEY, UNIQUE, FOREIGN KEY','Защищают идентичность и связи; ON CONFLICT использует существующие уникальные ограничения.'],
    ['NUMERIC(10,2)','Денежные вычисления выполняются точно до копейки; сравнение с Python использует Decimal.'],
    ['TIMESTAMPTZ','Время хранится с часовым поясом; месяц для отчёта выделяется в Europe/Moscow.'],
    ['CHECK и NOT NULL','Отрицательные и нулевые цены, платежи и количества не превращаются в допустимые строки.'],
    ['ON DELETE RESTRICT','Удаление родителя с зависимыми строками запрещено; DML демонстрирует правильный порядок удаления.']],[.37,.63],9.6)
heading('Историческая цена и третья нормальная форма')
para('<b>menu_items.price</b> - текущая цена меню. <b>order_items.unit_price</b> - цена конкретной продажи. Стоимость заказа вычисляется как SUM(quantity * unit_price). Изменение меню не переписывает старые чеки. Названия категорий, блюд и сотрудников по-прежнему хранятся в своих таблицах.')
code('ALTER TABLE orders\nADD COLUMN IF NOT EXISTS guest_note TEXT;')
para('Это единственное расширение схемы. Пожелание гостя относится к самому заказу; NULL означает, что пожелания нет. Старые поля и внешние ключи сохраняются, новая транзитивная зависимость не появляется.')
callout('Какая именно версия ЛР 1 проверена','Использованы lab_01/schema.sql и lab_01/data.sql с текстовым orders.status. Описание status_code в README первой работы относится к другой версии схемы. lab_01/migration.sql в проверяемую цепочку не входит. Для изменённой вручную базы следует воспроизвести запуск с нуля по инструкции на стр. 28.',accent=AMBER)
end()


def counts_chart(w,h):
    before=DATA['before'];after=DATA['after'];scale=(w-172)/103
    for n,name in enumerate(before):
        yy=h-29-n*29
        text(0,yy+2,name,9,'#17324D')
        for count,offset,col in [(len(before[name]),7,colors.HexColor('#9BB9CF')),(len(after[name]),-3,TEAL)]:
            C.setFillColor(col);C.roundRect(125,yy+offset,max(2,count*scale),7,2,fill=1,stroke=0)
            text(130+count*scale,yy+offset-1,str(count),8,col)
    text(125,4,'Светлый: ЛР 1     Зелёный: после расширения ЛР 2',9,GRAY)


begin('1.1. Как сформирован набор данных')
para('В исходной базе было 42 строки, в том числе 5 заказов. Скрипт prepare_data.sql добавляет 160 строк: сотрудников, столики, категории, блюда, 36 заказов, 90 позиций и 24 оплаты. Всего получается 202 строки.')
figure(242,counts_chart,'Рисунок 3. Размеры реальных таблиц до и после расширения. Источник: снимки B01.')
table(['Требование','Факт','Проверка'],[
    ['Не менее 100 строк','202 суммарно в семи таблицах','D01: PASS'],
    ['Не менее 30 операционных строк','41 заказ в orders; также 103 позиции','D02: PASS'],
    ['Не менее трёх состояний','open: 7; closed: 25; cancelled: 9','D03: PASS'],
    ['Не менее трёх месяцев','Август, сентябрь, октябрь 2026 года','D04: PASS'],
    ['Повторяющиеся операции','Анна: 14 заказов; Борис: 14; Дмитрий: 12','D05: PASS']],[.34,.48,.18],9.4)
para('Шаблон номера L2-YYYYMM-DD отражает месяц и день учебного заказа. Первые пять номеров R-101-R-105 сохраняются. Август и сентябрь намеренно повторяют один сценарий посещений; октябрь дополнительно содержит исходные операции ЛР 1.')
small('Сохранность проверялась по значениям всех исходных столбцов каждой исходной строки, а не только по количеству записей. Результат: B01 PASS.')
end()


def status_chart(w,h):
    palette=[GREEN,BLUE,AMBER]
    for idx,(month,vals) in enumerate([('Август',[7,2,3]),('Сентябрь',[7,2,3]),('Октябрь',[11,3,3])]):
        yy=h-35-idx*40;text(0,yy+5,month,10)
        xx=90
        for v,col in zip(vals,palette):
            ww=v*(w-105)/17;C.setFillColor(col);C.rect(xx,yy,ww,23,fill=1,stroke=0)
            text(xx+ww/2-3,yy+7,str(v),10,colors.white,'Bold');xx+=ww
    for i,(label,col) in enumerate(zip(['closed','open','cancelled'],palette)):
        C.setFillColor(col);C.rect(i*145+70,3,10,10,fill=1,stroke=0);text(i*145+86,3,label,9,GRAY)


begin('Данные для нетривиальных случаев')
figure(155,status_chart,'Рисунок 4. Распределение состояний по месяцам: 25 закрытых, 7 открытых и 9 отменённых заказов.')
table(['Ситуация','Конкретные строки','Зачем нужна'],[
    ['Нет операций','Елена Орлова; столик № 6','Проверка сохранения нулевых групп.'],
    ['Блюдо без заказов','Панна-котта; Тыквенный суп','LEFT JOIN с поиском отсутствия.'],
    ['Пустой заказ','Заказы 04 и 06 каждого месяца: всего 6','Нулевая сумма без нарушения CHECK.'],
    ['Несколько оплат','Заказ 02 каждого месяца: 40% + 60%','Проверка отсутствия удвоения сумм.'],
    ['Частичная оплата','Закрытые 03, открытые 10','Различие частичного долга и отсутствия оплаты.'],
    ['Нет оплаты','Закрытые 09 каждого месяца','Осмысленный NOT EXISTS; обнаружение ошибки процесса.'],
    ['NULL и границы','35 guest_note IS NULL; seats = 1 и 20','Допустимое отсутствие значения и границы CHECK.']],[.23,.40,.37],9.4)
callout('Почему ноль здесь корректен','В цену, количество и платёж нельзя записать 0: исходные CHECK требуют значения &gt; 0. Нулевая стоимость получается у заказа без позиций; нулевые продажи - у категории без закрытых заказов. Для сотрудника без чеков средний чек остаётся NULL.')
small('Подтверждение: D06-D07; реальные строки сохранены в report/evidence.json. Отсутствие полной оплаты у закрытого заказа разрешено схемой ЛР 1, поэтому это тест аналитики, а не нарушение FK или CHECK.')
end()


def transaction(w,h):
    entries=[('ДО BEGIN','open','520 / 440'),('В ТРАНЗАКЦИИ','cancelled','468 / 396'),('ПОСЛЕ ROLLBACK','open','520 / 440')]
    bw=(w-38)/3
    for i,(title,status,prices) in enumerate(entries):
        box(i*(bw+19),27,bw,103,title,'Заказ 06: '+status+'<br/>Цены: '+prices,fill=LIGHT if i!=1 else colors.HexColor('#FFF1DC'))
        if i<2:arrow(i*(bw+19)+bw+3,80,(i+1)*(bw+19)-4,80)
    text(0,5,'Строки восстановлены; значения последовательностей IDENTITY не откатываются.',8.8,GRAY)


begin('1.2. Изменение данных: DML')
figure(143,transaction,'Рисунок 5. Изменения видны внутри транзакции, после ROLLBACK исходные значения возвращаются.')
heading('1. Добавление сущности и связанных записей')
para('Создаётся тестовый официант, затем заказ L2-DML-DEMO с его staff_id, затем две позиции заказа. Ссылки на блюда и столик получаются через SELECT по предметным ключам. Возвращаемые значения показаны в RETURNING: вставлены 1 сотрудник, 1 заказ и 2 позиции.')
heading('2. Изменение состояния существующей операции')
code("UPDATE orders SET status = 'cancelled'\nWHERE order_number = 'L2-202608-06' AND status = 'open'\nRETURNING order_number, status;")
para('Затронут один существующий заказ. Он пуст и не имеет оплат: отмена не требует возврата денег, которого нет в исходной модели.')
heading('3. Массовое изменение по предметному условию')
code("UPDATE menu_items AS mi\nSET price = ROUND(mi.price * 0.90, 2)\nFROM menu_categories AS c\nWHERE mi.category_id = c.id AND c.name = 'Десерты'\n  AND mi.is_available AND mi.price > 300.00\nRETURNING mi.name, mi.price;")
para('Условие выбирает доступные десерты дороже 300 рублей: изменены две строки. Исторические unit_price в order_items этим UPDATE не затрагиваются.')
small('Источник: lab_02/dml.sql. Все операции заключены между BEGIN и ROLLBACK.')
end()

begin('Удаление, целостность и откат')
heading('4. Почему нельзя начать с удаления сотрудника')
para('Заказ ссылается на staff.id через внешний ключ с ON DELETE RESTRICT. DELETE родителя отклоняется. Внутренний блок DO перехватывает именно foreign_key_violation; неожиданное успешное удаление вызвало бы исключение и остановило общий запуск.')
code("DELETE FROM order_items\nWHERE order_id = (SELECT id FROM orders\n                  WHERE order_number = 'L2-DML-DEMO');\nDELETE FROM orders WHERE order_number = 'L2-DML-DEMO';\nDELETE FROM staff WHERE email = 'lab02.demo@restaurant.example';\nROLLBACK;")
para('Правильная последовательность удаления демонстрационных строк: дочерние позиции, заказ, сотрудник. В демонстрационном заказе нет платежей, поэтому удалять payments не требуется.')
heading('5. Как проверено восстановление')
para('До BEGIN создаётся временный JSONB-снимок всех строк staff, menu_items, orders и order_items. После ROLLBACK снимок каждой таблицы сравнивается с её текущим содержимым через IS DISTINCT FROM. Несовпадение вызывает RAISE EXCEPTION.')
code('Фактические сообщения psql:\nУдаление сотрудника с заказом отклонено внешним ключом\nROLLBACK проверен: строки всех затронутых таблиц восстановлены')
table(['Контроль','Внутри транзакции','После ROLLBACK'],[
    ['L2-202608-06','cancelled','open'],['Чизкейк, руб.','468,00','520,00'],
    ['Панна-котта, руб.','396,00','440,00'],['Тестовый сотрудник и заказ','Созданы, затем удалены','Отсутствуют']],[.40,.30,.30],10)
small('Подтверждение: B02-B03 PASS. Сообщения взяты из реального запуска; это текстовый фрагмент вывода, переоформленный для чтения. IDENTITY может иметь пропуски - это нормальное свойство PostgreSQL.')
end()

begin('2.1.1. Подробная информация о заказах')
para('<b>Вопрос:</b> какие блюда входили в неотменённые заказы октября, кто обслуживал заказ и за каким столиком? Одна строка результата - одна позиция заказа.')
query_code('2.1.1')
heading('Как читать запрос')
para('orders задаёт операцию. staff и dining_tables дают сотрудника и столик; order_items, menu_items и menu_categories раскрывают состав. Шесть таблиц соединяются по внешним ключам. Полуоткрытый интервал дат включает весь октябрь и исключает начало ноября.')
table(['Заказ R-101','Количество','Цена, руб.','Стоимость, руб.'],[
    ['Брускетта','1','350,00','350,00'],['Паста','2','690,00','1 380,00'],
    ['Чай','2','220,00','440,00'],['Итого','','','2 170,00']],[.40,.18,.20,.22],9.5)
para('Контрольный исходный заказ R-101 из ЛР 1 даёт 350 + 2 × 690 + 2 × 220 = 2 170 рублей. SQL использует unit_price, поэтому будущая смена menu_items.price не изменит результат.')
small('Факт: 37 строк позиций. Q211 PASS: весь набор строк совпал с независимым соединением исходных данных. Пустые заказы ожидаемо отсутствуют из-за INNER JOIN к order_items.')
end()


def leftjoin(w,h):
    box(0,42,143,100,'menu_items','Панна-котта<br/>Тыквенный суп')
    box(182,42,143,100,'LEFT JOIN','Нет order_items<br/>oi.id = NULL')
    box(365,42,w-365,100,'Результат','Обе строки сохранены<br/>COALESCE(quantity, 0)')
    arrow(147,91,177,91);arrow(330,91,359,91)
    text(4,13,'WHERE oi.id IS NULL оставляет именно строки без дочерних записей.',9.4,GRAY)


begin('2.1.2. Блюда без связанных операций')
para('<b>Вопрос:</b> какие блюда ни разу не включали в заказ? Это помогает увидеть позиции меню без спроса или ещё не запущенные предложения.')
query_code('2.1.2')
figure(160,leftjoin,'Рисунок 6. LEFT JOIN сохраняет левую сущность, когда справа нет ни одной связанной строки.')
result('2.1.2',['category','item','price','ordered_portions'],['Категория','Блюдо','Цена','Порции'],widths=[.29,.31,.20,.20],size=9.3)
heading('Почему условие корректно')
para('Проверяется oi.id - первичный ключ позиции. В реальной строке он всегда NOT NULL, поэтому NULL после LEFT JOIN однозначно означает отсутствие совпадения. Проверка nullable атрибута вроде пожелания гостя такого вывода сделать бы не позволила.')
para('В запросе ровно три таблицы: menu_items, menu_categories и order_items. INNER JOIN вместо LEFT JOIN потерял бы оба искомых блюда. COALESCE показывает ноль только в выводе и не записывает недопустимое количество 0 в таблицу.')
end()

begin('2.1.3. Несколько связанных условий')
para('<b>Вопрос:</b> какие закрытые заказы за столиками минимум на четыре места содержат основное блюдо и хотя бы одну оплату картой?')
query_code('2.1.3')
heading('Что подтверждает совместность условий')
para('Каждое соединение привязано к одному o.id: блюдо и платёж принадлежат тому же заказу, для которого проверяются статус и вместимость столика. Нельзя случайно подтвердить карту другого заказа или категорию другого блюда.')
table(['Пример','Проверяемые факты','Решение'],[
    ['L2-202608-02','closed; столик № 2 на 4 места; ризотто; есть card','Попадает'],
    ['L2-202608-01','closed; основное блюдо и card есть; столик на 2 места','Исключён'],
    ['L2-202608-09','closed; столик на 6 мест; паста; нет ни одной оплаты','Исключён']],[.26,.56,.18],9.5)
para('DISTINCT обеспечивает одну строку на заказ: несколько подходящих блюд или карточных платежей не создают дубликаты результата. Заказ не обязан быть полностью оплачен: условие требует наличия карточного платежа.')
small('Факт: 10 уникальных заказов. Q213 PASS: набор совпал с отдельной проверкой четырёх условий для каждого заказа. Источник: joins.sql, третий SELECT.')
end()

begin('2.2.1. Количество операций по группам')
para('<b>Вопрос:</b> сколько заказов у каждого сотрудника и как они распределены по трём состояниям?')
query_code('2.2.1')
result('2.2.1',['full_name','orders_count','open_count','closed_count','cancelled_count'],
    ['Сотрудник','Всего','Открыто','Закрыто','Отменено'],widths=[.36,.15,.16,.16,.17],size=9.5)
heading('COUNT(o.id) и COUNT(*) здесь различаются')
para('Для Елены Орловой LEFT JOIN создаёт одну результирующую строку с NULL в полях orders. COUNT(*) посчитал бы эту техническую строку и дал 1. COUNT(o.id) игнорирует NULL и правильно возвращает 0. FILTER считает только нужное состояние.')
callout('Контрольные равенства','Анна: 3 + 8 + 3 = 14. Борис: 1 + 10 + 3 = 14. Дмитрий: 3 + 6 + 3 = 12. Сумма всех orders_count = 41 - ровно число заказов в базе.')
small('GROUP BY содержит id сотрудника и его имя. Поэтому даже сотрудники с одинаковыми именами не будут объединены в одну сущность.')
end()

begin('2.2.2. Продажи и средний чек с HAVING')
para('<b>Вопрос:</b> какие сотрудники оформили закрытые заказы минимум на 10 000 рублей, каковы их средний, минимальный и максимальный чеки?')
query_code('2.2.2')
result('2.2.2',['full_name','closed_count','closed_sales','average_check','min_check','max_check'],
    ['Сотрудник','Чеков','Сумма','Средний','Мин.','Макс.'],widths=[.28,.11,.17,.16,.14,.14],size=8.7)
para('Внутренний SELECT сначала сворачивает позиции до одного итога на order_id. Поэтому AVG считает среднее по заказам, а не по позициям. Анна: 26 510 / 8 = 3 313,75 рубля. У Марии 2 150 рублей, поэтому её группа отсеивается.')
callout('WHERE и HAVING выполняют разные задачи','WHERE o.status = closed отбирает исходные операции до группировки. HAVING SUM(...) &gt;= 10000 отбирает уже сформированные группы. Здесь использованы все пять требуемых агрегатов: COUNT, SUM, AVG, MIN, MAX.')
end()

begin('2.2.3. Сравнение категорий по месяцам')
para('<b>Вопрос:</b> сколько порций и на какую сумму продано в каждой категории в каждом месяце, включая категории с нулевыми продажами?')
query_code('2.2.3')
heading('Порядок вычисления')
para('1. Выбираются три месяца, присутствующие в orders. 2. CROSS JOIN создаёт 3 × 5 = 15 пар «месяц - категория». 3. LEFT JOIN присоединяет блюда, позиции и закрытые заказы соответствующего месяца. 4. GROUP BY сворачивает строки каждой пары.')
para('FILTER (WHERE o.id IS NOT NULL) допускает в суммы только позиции, для которых нашёлся закрытый заказ нужного месяца. Это существенно: после LEFT JOIN сама позиция может существовать, хотя подходящий заказ справа отсутствует.')
small('Факт: 15 строк. Q223 PASS. COUNT(DISTINCT o.id) не дублирует заказ, если он содержит несколько блюд одной категории. Числа заказов разных категорий нельзя складывать между собой: один заказ может относиться к нескольким категориям.')
end()


def sales_chart(w,h):
    rows=DATA['queries']['2.2.3']['rows']
    mths=['2026-08-01','2026-09-01','2026-10-01']
    cats=['Десерты','Закуски','Напитки','Основные блюда','Сезонное меню']
    pal=[colors.HexColor('#8599BF'),colors.HexColor('#E1A44B'),TEAL,BLUE,GRAY]
    maxsum=max(sum(Decimal(str(r['sales'])) for r in rows if r['month']==m) for m in mths)
    for idx,m in enumerate(mths):
        yy=h-39-idx*44;text(0,yy+6,['Август','Сентябрь','Октябрь'][idx],10)
        xx=83
        for name,col in zip(cats,pal):
            val=next(Decimal(str(r['sales'])) for r in rows if r['month']==m and r['category']==name)
            ww=float(val/maxsum)*(w-150)
            if ww:
                C.setFillColor(col);C.rect(xx,yy,ww,24,fill=1,stroke=0);xx+=ww
        total=sum(Decimal(str(r['sales'])) for r in rows if r['month']==m)
        text(xx+5,yy+7,str(int(total)),9,BLUE,'Bold')
    for idx,name in enumerate(cats):
        xx=(idx%3)*165;yy=20-(idx//3)*18
        C.setFillColor(pal[idx]);C.rect(xx,yy,8,8,fill=1,stroke=0);text(xx+13,yy,name,8.5,GRAY)


begin('Как читать сравнение продаж')
figure(195,sales_chart,'Рисунок 7. Стоимость позиций закрытых заказов по месяцам и категориям, рубли. Сезонное меню имеет нулевые продажи.')
rows=DATA['queries']['2.2.3']['rows']
table(['Месяц','Категория','Заказов','Порций','Сумма, руб.'],[
    [r['month'][5:7]+'.2026',r['category'],r['orders_count'],r['portions'],money(r['sales'])] for r in rows],
    [.15,.35,.15,.15,.20],8.9)
para('Контроль: за август суммы категорий равны 300 + 2 100 + 3 680 + 12 160 + 0 = 18 240 рублей. Это совпадает с closed_sales итогового CTE-отчёта за тот же месяц. За октябрь аналогичная сумма равна 26 930 рублей.')
small('Одинаковые показатели августа и сентября объясняются повторением сценария тестовых посещений, а не потерей временной фильтрации: каждый месяц проверен независимо по opened_at.')
end()

begin('3.1. Сравнение со средним своей группы')
para('<b>Вопрос:</b> какие блюда стоят дороже среднего в своей категории? В качестве группы сравнения используется menu_items.category_id.')
query_code('3.1')
result('3.1',['category','item','price','category_average'],['Категория','Блюдо','Цена','Среднее группы'],widths=[.28,.30,.18,.24],size=9.5)
heading('Ручная проверка')
para('Десерты: (520 + 300 + 440) / 3 = 420 рублей. Чизкейк за 520 и панна-котта за 440 выше среднего; мороженое за 300 - ниже. В закусках среднее равно 483,333...: сырная тарелка за 620 проходит, цезарь за 480 - нет.')
callout('Почему группа определена корректно','Условие peer.category_id = mi.category_id связывает подзапрос с категорией текущего блюда. Сравнение выполняется с точным AVG; ROUND используется только при выводе. Поэтому округление среднего не меняет состав результата.')
small('Подтверждение: Q31 PASS, все 5 строк совпали с независимым расчётом по группам.')
end()

begin('3.2. EXISTS: наличие нужного события')
para('<b>Вопрос:</b> у каких сотрудников существует хотя бы один закрытый заказ с оплатой наличными?')
query_code('3.2')
result('3.2',['full_name','email'],['Сотрудник','Email'],widths=[.35,.65],size=10)
heading('Что проверяет EXISTS')
para('Для текущего сотрудника s подзапрос ищет связанный заказ o и его платёж p. Необходимы одновременно три условия: o.staff_id = s.id, статус closed и метод cash. Достаточно одного подходящего совпадения.')
table(['Сотрудник','Контрольный пример','Результат'],[
    ['Анна Иванова','Исходный закрытый R-101 имеет наличный платёж 1 000 рублей','Есть'],
    ['Борис Петров','Учебные закрытые заказы 02 имеют наличную часть 40%','Есть'],
    ['Дмитрий Смирнов','В его заказах нет наличных платежей','Нет'],
    ['Елена Орлова','Нет заказов вообще','Нет']],[.28,.56,.16],9.4)
callout('Почему сотрудник выводится один раз','Внешняя выборка идёт только по staff. EXISTS возвращает логическое значение, поэтому два наличных платежа не создадут две строки сотрудника.')
end()

begin('3.3. NOT EXISTS: отсутствие события')
para('<b>Вопрос:</b> какие закрытые непустые заказы не имеют ни одного платежа? Это конкретный сигнал для проверки расчётов с гостем.')
query_code('3.3')
result('3.3',['order_number','full_name','unpaid_amount'],['Заказ','Сотрудник','Не оплачено, руб.'],widths=[.31,.37,.32],size=10)
para('Для каждого заказа 09: паста 2 × 690 + чай 2 × 220 + брускетта 350 = 2 170 рублей. Платежей нет, а статус closed. Всего три таких заказа - по одному в месяц.')
callout('Отсутствие оплаты и неполная оплата различаются','Заказ 03 оплачен наполовину: платёж существует, поэтому NOT EXISTS для него ложно. Он не входит в этот результат, но попадает в задолженность CTE-отчёта. Пустой заказ не создаёт долг и исключается INNER JOIN с таблицей сумм позиций.')
small('Подтверждение: Q33 PASS. Само по себе closed без оплаты не нарушает ограничения исходной схемы: межтабличное правило полной оплаты в ЛР 1 не реализовано.')
end()

begin('3.4. Коррелированный подзапрос')
para('<b>Вопрос:</b> каковы средний чек закрытых заказов и время последнего заказа каждого конкретного сотрудника?')
query_code('3.4')
result('3.4',['full_name','average_closed_check','last_order_at'],['Сотрудник','Средний чек','Последний заказ'],widths=[.31,.25,.44],size=9.1)
heading('Где находится корреляция')
para('Оба подзапроса содержат o.staff_id = s.id. Значение s.id берётся из текущей строки внешнего SELECT. Без этого условия у всех сотрудников получилось бы одно общее среднее и одна общая дата.')
para('У Елены нет заказов: AVG и MAX возвращают NULL. Это означает «значение не определено», а не «средний чек равен 0». Внутренний LEFT JOIN и COALESCE, напротив, дают нулевую сумму для существующего пустого закрытого заказа, если такой появится.')
small('Подтверждение: Q34 PASS. Средний чек Анны совпадает с запросом 2.2.2: 3 313,75 рубля.')
end()


def cte_flow(w,h):
    box(0,h-78,w,64,'ИСХОДНЫЕ ТАБЛИЦЫ','orders + order_items + payments + staff')
    bw=(w-24)/2
    box(0,h-180,bw,69,'item_totals','SUM(quantity × unit_price)<br/>Одна строка на заказ')
    box(bw+24,h-180,bw,69,'payment_totals','SUM(amount)<br/>Одна строка на заказ')
    arrow(w/4,h-83,w/4,h-105);arrow(3*w/4,h-83,3*w/4,h-105)
    box(0,h-283,w,69,'order_metrics','Стоимость, оплачено, положительный остаток,<br/>статус, сотрудник, месяц открытия заказа')
    arrow(w/4,h-184,w/2-40,h-208);arrow(3*w/4,h-184,w/2+40,h-208)
    box(0,h-380,w,65,'monthly_summary','GROUP BY month, staff_id; суммы и количества по статусам')
    arrow(w/2,h-288,w/2,h-309)
    box(0,8,w,68,'ИТОГОВЫЙ ОТЧЁТ','months × staff + LEFT JOIN monthly_summary<br/>15 строк; нули для отсутствующих операций; процент оплаты',fill=colors.HexColor('#E7F5F1'),color=TEAL)
    arrow(w/2,h-385,w/2,82)


begin('4. Схема вычислений CTE-отчёта')
para('<b>Вопрос управляющего:</b> какие сотрудники обеспечили продажи каждого месяца, сколько получено по закрытым заказам и какой долг остался?')
figure(478,cte_flow,'Рисунок 8. Исходные данные -> промежуточные показатели -> агрегация -> итоговый отчёт.')
para('Месяц берётся по дате открытия заказа в часовом поясе ресторана. Платежи относятся к этому заказу независимо от paid_at. Отчёт описывает расчёты по заказам месяца, а не движение денег по календарным датам платежей.')
small('Источник: cte_report.sql. Все CTE являются частями одного SQL-запроса, отдельные постоянные таблицы для отчёта не создаются.')
end()


def fanout(w,h):
    bw=(w-24)/2
    box(0,h-56,bw,45,'Прямой JOIN: ошибка сумм',fill=colors.HexColor('#FCEDEC'),color=RED)
    box(bw+24,h-56,bw,45,'Предварительная агрегация',fill=colors.HexColor('#E7F5F1'),color=TEAL)
    yy=h-85
    for i,(a,b) in enumerate([('720','648'),('720','972'),('600','648'),('600','972'),('300','648'),('300','972')]):
        text(12,yy-i*22,'Позиция '+a+'  |  Оплата '+b,9.5)
    text(12,yy-155,'3 позиции × 2 оплаты = 6 строк',10,RED,'Bold')
    text(12,yy-178,'SUM(позиции) = 3 240  [ошибка]',10,RED)
    text(12,yy-199,'SUM(оплаты) = 4 860   [ошибка]',10,RED)
    xx=bw+37
    text(xx,yy,'Позиции: 720 + 600 + 300',10)
    text(xx,yy-24,'item_totals = 1 620',11,TEAL,'Bold')
    text(xx,yy-66,'Платежи: 648 + 972',10)
    text(xx,yy-90,'payment_totals = 1 620',11,TEAL,'Bold')
    arrow(xx+70,yy-106,xx+70,yy-137,TEAL)
    text(xx,yy-161,'Одна строка заказа:',10)
    text(xx,yy-186,'1 620 - 1 620 = 0 долга',11,TEAL,'Bold')


begin('Почему суммы не удваиваются')
para('Контрольный заказ L2-202608-02 содержит три позиции общей стоимостью 1 620 рублей и две оплаты: 648 рублей наличными и 972 рубля картой.')
figure(337,fanout,'Рисунок 9. Реальные значения одного заказа показывают ошибку прямого соединения двух связей «один ко многим».')
para('Прямой JOIN order_items и payments по order_id размножает каждую позицию на число оплат, а каждый платёж - на число позиций. DISTINCT над итоговой суммой эту ошибку не исправляет. SUM(DISTINCT amount) тоже не является общим решением: разные оплаты могут иметь одинаковую сумму.')
callout('Инвариант корректного отчёта','После item_totals и payment_totals каждому order_id соответствует максимум одна строка в каждом наборе. Поэтому LEFT JOIN в order_metrics сохраняет ровно одну строку на заказ и не меняет кратность его суммы.')
small('Подтверждение Q4 PASS: независимо проверены все 15 строк и все 12 полей отчёта, включая деньги, состояния, нулевые группы и долю оплаты.')
end()

begin('CTE-отчёт: SQL, часть 1')
para('Начало того же единственного запроса. Первые CTE вычисляют суммы и соединяют их с заказами. Код приведён из проекта без служебных комментариев.')
full=DATA['queries']['4']['sql']
cut=full.index('monthly_summary AS')
code(full[:cut].rstrip(),7.8)
heading('Какие значения получаются для одного заказа')
table(['Заказ','Стоимость','Оплачено','Остаток','Статус'],[
    ['L2-202608-02','1 620','1 620','0','closed'],
    ['L2-202608-03','2 170','1 085','1 085','closed'],
    ['L2-202608-06','0','0','0','open'],
    ['L2-202608-09','2 170','0','2 170','closed']],[.30,.18,.18,.16,.18],9.5)
para('COALESCE заменяет отсутствие позиций или оплат на 0. GREATEST(..., 0) делает остаток неотрицательным. Далее остатки закрытых и открытых заказов учитываются в разных показателях.')
small('Запятая в конце показанного фрагмента соединяет его с monthly_summary на следующей странице. Это разделение вёрстки, а не два запроса.')
end()

begin('CTE-отчёт: SQL, часть 2')
code(full[cut:].strip()+';',7.3)
para('FILTER разделяет статусы внутри одной группы. CROSS JOIN months и staff сохраняет каждого сотрудника во всех представленных месяцах. NULLIF защищает деление от нулевого объёма продаж.')
small('Доля оплаты может быть NULL: отсутствие продаж не позволяет вычислить процент. В наборе нет переплат; при их появлении collected может превысить closed_sales, а closed_debt по-прежнему считается отдельно по каждому заказу.')
end()

begin('Итоговый отчёт: проверка чисел')
table(['Месяц','Продажи закрытых','Получено','Долг','Заказов с долгом','Открытый остаток'],[
    ['Август','18 240,00','14 985,00','3 255,00','2','1 235,00'],
    ['Сентябрь','18 240,00','14 985,00','3 255,00','2','1 235,00'],
    ['Октябрь','26 930,00','23 675,00','3 255,00','2','2 145,00'],
    ['Всего','63 410,00','53 645,00','9 765,00','6','4 615,00']],
    [.15,.19,.17,.17,.15,.17],9.2)
heading('Ручная проверка долга Дмитрия за август')
para('У него два закрытых заказа по 2 170 рублей: 03 и 09. По 03 получено 1 085 рублей, по 09 - 0. Продажи: 4 340. Получено: 1 085. Долг: (2 170 - 1 085) + (2 170 - 0) = 3 255. Доля оплаты: 1 085 / 4 340 × 100 = 25%.')
table(['Сотрудник, август','Заказов','Продажи','Получено','Долг','Оплачено, %'],[
    [r['full_name'],r['orders_count'],money(r['closed_sales']),money(r['collected']),money(r['closed_debt']),value(r['collection_percent'])]
    for r in DATA['queries']['4']['rows'] if r['month']=='2026-08-01'],
    [.29,.12,.16,.16,.15,.12],9)
heading('Проверки согласованности')
para('В этом наборе нет переплат, поэтому 63 410 - 53 645 = 9 765 рублей. Долг не отменяется оплатами по открытым или отменённым заказам. Стоимость закрытых заказов по категориям совпадает с closed_sales по сотрудникам для каждого месяца.')
callout('Граница интерпретации','Статусы берутся текущие на момент запроса. Отчёт не восстанавливает состояние базы на конец прошлого месяца: для такого исторического отчёта потребовалась бы согласованная история переходов статусов. Также эти 3 месяца не включают месяцы, вообще отсутствующие в orders.')
small('Источник: фактический результат cte_report.sql; Q4 PASS. Полные 15 строк доступны в report/evidence.json и results.txt.')
end()

begin('Как проверялась корректность')
para('Проверка выполнялась в отдельном временном экземпляре PostgreSQL 17.11. Существующие пользовательские базы не использовались. После проверки временный сервер остановлен и его файлы удалены.')
table(['Шаг','Что выполнено','Критерий успеха'],[
    ['1. Исходная база','Выполнены schema.sql и data.sql из ЛР 1, снят полный снимок семи таблиц','42 исходные строки сохранены для сравнения.'],
    ['2. Полный запуск','run_all.sql выполнен с ON_ERROR_STOP=1','Нет неперехваченных ошибок; проверки DML и данных прошли.'],
    ['3. Сохранность','Каждая исходная строка найдена по id, сравнены все исходные поля','Ни одна строка и ни одно старое значение не потеряны.'],
    ['4. Ограничения','После расширения выполнен constraints_test.sql из ЛР 1','Все 8 отрицательных проверок отклоняют недопустимые операции.'],
    ['5. Независимый расчёт','На Python по строкам таблиц отдельно вычислены результаты всех 11 запросов','Совпадает состав строк и каждое выводимое значение.'],
    ['6. Повторный запуск','Ещё раз выполнен весь run_all.sql и снят полный снимок','Содержимое всех семи таблиц совпадает с первым запуском.']],[.22,.42,.36],9.7)
heading('Что делает независимый расчёт')
para('Он не повторяет SQL через другой SELECT. Проверяющий сценарий читает исходные строки в Python, строит связи по идентификаторам, отдельно суммирует позиции и платежи, отбирает объекты и группирует их. Денежные значения обрабатываются Decimal, округление - до копейки.')
callout('Что именно сравнивалось','Проверены 37 строк детализации, 2 блюда без заказов, 10 заказов с совместными условиями, все группировки, все подзапросы и 15 строк CTE-отчёта. Числа строк сами по себе не служили достаточной проверкой: сравнивались значения каждой строки.')
small('Точность источников фиксируется SHA-256 всех проверенных SQL-файлов в report/evidence.json. Скрипт: report/verify_report.py. Всего 24 проверки PASS; B04 включает ещё 8 исходных проверок ограничений.')
end()

begin('Матрица требований: часть 1')
para('Каждый пункт задания сопоставлен с реализацией и конкретным подтверждением. PASS означает, что указанный критерий проверен на текущей версии файлов и тестовых данных.')
table(['Пункт задания','Реализация','Подтверждение'],[
    ['Модель ЛР 1 сохранена','Те же 7 таблиц и связи; добавлен только guest_note','B01 PASS; схема на стр. 3-4.'],
    ['Не менее 100 записей','prepare_data.sql','D01 PASS: 202 строки.'],
    ['Не менее 30 операционных записей','Основная таблица orders','D02 PASS: 41 заказ.'],
    ['Три состояния','open, closed, cancelled','D03 PASS: 7 / 25 / 9.'],
    ['Три календарных месяца','Август, сентябрь, октябрь 2026','D04 PASS: 3 разных месяца.'],
    ['Повторные операции','Один сотрудник обслуживает несколько заказов','D05 PASS: 14, 14 и 12 заказов.'],
    ['Нет связанных операций','Елена без заказов; блюда без позиций','D06, Q212 PASS.'],
    ['Нули и NULL','Пустые заказы, нулевые продажи, необязательное пожелание','D07 PASS: 6 пустых заказов, 35 NULL.'],
    ['INSERT сущности и связей','Тестовый сотрудник, его заказ и 2 позиции','run_all.txt: INSERT 1 + 1 + 2.'],
    ['UPDATE состояния','open -> cancelled у L2-202608-06','run_all.txt: UPDATE 1.'],
    ['Массовое изменение','Скидка на доступные десерты дороже 300','run_all.txt: UPDATE 2.'],
    ['DELETE с целостностью','Показан запрет FK, затем удаление детей и родителя','B03 PASS; DELETE 2 + 1 + 1.'],
    ['ROLLBACK','Откат и сравнение снимков четырёх таблиц','B02 PASS: полное равенство строк.']],[.29,.40,.31],9.1)
small('Связь с оригинальным заданием: общая постановка и часть 1 PDF «Лабораторная работа № 2», стр. 1. Реализация: prepare_data.sql, dml.sql; объяснение в этом документе на стр. 3-8.')
end()

begin('Матрица требований: часть 2')
table(['Пункт задания','Реализация','Подтверждение'],[
    ['3 JOIN-запроса, минимум 3 таблицы','Детали: 6; отсутствие: 3; условия: 7 таблиц','Q211-Q213 PASS; стр. 9-11.'],
    ['LEFT JOIN и отсутствие записей','Блюда без позиций, проверка oi.id IS NULL','Q212 PASS: 2 блюда.'],
    ['Количество операций по группам','Заказы сотрудника по трём состояниям','Q221 PASS: 5 групп, включая нулевую.'],
    ['Сумма/среднее и HAVING','Закрытые заказы сотрудника от 10 000 рублей','Q222 PASS: 3 группы.'],
    ['Сравнение категорий/периодов','Категории в каждом из трёх месяцев','Q223 PASS: 15 строк.'],
    ['Минимум 3 агрегатные функции','COUNT, SUM, AVG, MIN, MAX','Все 5 есть в aggregates.sql.'],
    ['Показатель выше среднего группы','Цена выше AVG по своей category_id','Q31 PASS: 5 блюд.'],
    ['EXISTS с дополнительным условием','Закрытый заказ и оплата cash','Q32 PASS: 2 сотрудника.'],
    ['NOT EXISTS с предметным смыслом','Закрытый непустой заказ без оплат','Q33 PASS: 3 заказа.'],
    ['Коррелированный подзапрос','Два условия o.staff_id = s.id','Q34 PASS: 5 строк, NULL у Елены.'],
    ['Один комплексный CTE-запрос','Продажи и задолженность по месяцу и сотруднику','Q4 PASS: все 15 строк и 12 полей.'],
    ['Схема вычислений и объяснение этапов','Исходные данные -> суммы -> метрики -> группы -> отчёт','Стр. 20-24; CTE в одном запросе.'],
    ['Дополнительно: повторяемость','Повторный run_all.sql, сравнение всех строк','B06 PASS: без дублей и изменений.']],[.30,.40,.30],9.1)
callout('Дополнительное подтверждение связи с ЛР 1','После выполнения ЛР 2 повторно прошли все исходные проверки UNIQUE, CHECK, FK и NOT NULL из constraints_test.sql. Примеры: отклонены отрицательная цена, нулевое количество и платёж, повтор блюда в заказе и ссылка на несуществующее блюдо.')
small('Связь с заданием: части 2-4 исходного PDF, стр. 2-3. Полный протокол: report/verification.txt; исходные результаты каждого SELECT: report/evidence.json.')
end()

begin('Воспроизведение и защита работы')
heading('Запуск с нуля на исходной модели')
code('cd /Users/myshakinm/study/database_labs\ncreatedb restaurant_lab14_lab02\npsql -X -v ON_ERROR_STOP=1 -d restaurant_lab14_lab02 \\\n  -f lab_01/schema.sql \\\n  -f lab_01/data.sql \\\n  -f lab_02/run_all.sql')
para('Имя создаваемой базы должно быть свободным. schema.sql и data.sql загружают исходную модель первой работы; run_all.sql дополняет её, показывает DML, выполняет 11 запросов и проверяет данные. При готовой совместимой базе достаточно последнего -f с её именем в -d.')
heading('Повторить независимую проверку')
code('python3 lab_02/report/verify_report.py')
para('Нужны команды initdb, pg_ctl и psql в PATH и разрешение на запуск локального PostgreSQL. Проверка сама создаёт временный кластер, сохраняет evidence.json, verification.txt и run_all.txt, затем удаляет временную базу. Рабочие базы не затрагиваются.')
heading('Короткие ответы на вопросы защиты')
table(['Вопрос','Ответ'],[
    ['Почему 11 запросов?','3 многотабличных + 3 группировки + 4 подзапроса + 1 комплексный CTE.'],
    ['Почему у Елены NULL и 0?','Нет заказов: количество 0; среднее и последняя дата не определены.'],
    ['Зачем две цены?','Цена меню меняется, цена позиции фиксирует состоявшуюся продажу.'],
    ['Почему продажи не равны оплатам?','В тестовых данных есть закрытые неоплаченные и частично оплаченные заказы.'],
    ['Зачем несколько CTE?','Нужны независимые суммы по заказу и явные этапы агрегации без размножения строк.'],
    ['Почему не migration.sql из ЛР 1?','Проверенная цепочка использует исходный orders.status; иная схема требует отдельной согласованной миграции.']],[.35,.65],9.3)
small('Файлы проекта являются первичным источником SQL. Этот PDF объясняет проверенную реализацию; в report/evidence.json находятся результаты и контрольные хеши файлов.')
end()

assert page_no==28,page_no
C.save()
(QA/'page_layout.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2))
print(str(PDF))
print('Pages:',page_no,'Lowest content boundary:',min(p['bottom'] for p in pages))
