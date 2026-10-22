"""Reference bill layout in points: 594.75 x 432, eight columns, carried totals.
Uses locally installed Windows fonts, with portable PDF built-in fallbacks.
"""
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from datetime import datetime
import os
import threading
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

WIDTH, HEIGHT = 594.75, 432
EDGES = [25.5,198,259.5,305.25,355.5,403.5,453,501,577.5]
_font_lock = threading.Lock()

def fonts():
    with _font_lock:
        folder = Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
        choices = [('Bill','verdana.ttf','Helvetica'),('BillBold','verdanab.ttf','Helvetica-Bold'),('BillTitle','timesbd.ttf','Times-Bold')]
        result = []
        for name,file,fallback in choices:
            if name not in pdfmetrics.getRegisteredFontNames() and (folder/file).exists():
                pdfmetrics.registerFont(TTFont(name,str(folder/file)))
            result.append(name if name in pdfmetrics.getRegisteredFontNames() else fallback)
        return result

def dec(value):
    return Decimal(str(value))

def amount(value):
    return f'{dec(value):.2f}'

def quantity(value):
    return format(dec(value),'f').rstrip('0').rstrip('.') if '.' in format(dec(value),'f') else str(value)

def words(n):
    n=int(n)
    small=['Zero','One','Two','Three','Four','Five','Six','Seven','Eight','Nine','Ten','Eleven','Twelve','Thirteen','Fourteen','Fifteen','Sixteen','Seventeen','Eighteen','Nineteen']
    tens=['','','Twenty','Thirty','Forty','Fifty','Sixty','Seventy','Eighty','Ninety']
    if n<20: return small[n]
    if n<100: return tens[n//10]+(' '+small[n%10] if n%10 else '')
    for size,name in [(10**12,'Trillion'),(10**9,'Billion'),(10**6,'Million'),(1000,'Thousand'),(100,'Hundred')]:
        if n>=size: return words(n//size)+' '+name+(' '+words(n%size) if n%size else '')

def rupees(value):
    value=dec(value).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    whole=int(value)
    paise=int((value-whole)*100)
    return words(whole)+((' And '+words(paise)+' Paise') if paise else '')+' Only'

def wrap(text,font,size,width):
    """Wrap even long unbroken strings, preserving all text."""
    lines=[]
    for paragraph in str(text or '').splitlines() or ['']:
        line=''
        for word in paragraph.split():
            proposed=(line+' '+word).strip()
            if pdfmetrics.stringWidth(proposed,font,size)<=width:
                line=proposed
                continue
            if line: lines.append(line)
            line=''
            for char in word:
                if line and pdfmetrics.stringWidth(line+char,font,size)>width:
                    lines.append(line)
                    line=''
                line+=char
        lines.append(line)
    return lines

def render_bill(d):
    regular,bold,title=fonts()
    output=BytesIO()
    c=canvas.Canvas(output,pagesize=(WIDTH,HEIGHT))
    c.setTitle(f"Shivam Tiles - {d['kind']} {d['id']}")
    c.setAuthor('Shivam Tiles')
    def text(x,top,value,font=regular,size=8,align='left',max_width=None):
        value=str(value)
        if max_width:
            while size>5.5 and pdfmetrics.stringWidth(value,font,size)>max_width:
                size-=.25
        c.setFont(font,size)
        fn={'left':c.drawString,'right':c.drawRightString,'center':c.drawCentredString}[align]
        fn(x,HEIGHT-top,value)
    def line(x1,y1,x2,y2):
        c.line(x1,HEIGHT-y1,x2,HEIGHT-y2)
    # Data comes from saved line snapshots, not today's product values.
    prepared=[]
    for row in d['lines']:
        values=[row.get('product_name') or row['description'],row.get('brand',''),row.get('pack',''),row.get('grade',''),row.get('colour',''),quantity(row['quantity']),amount(row['unit_price']),amount(row['amount'])]
        cells=[wrap(v,regular,8,EDGES[i+1]-EDGES[i]-4) for i,v in enumerate(values)]
        prepared.append((row,cells))
    pages=[]
    page=[]
    used=0
    for row,cells in prepared:
        height=max(len(cell) for cell in cells)*9.75
        capacity=175.5-(9.75 if pages else 0)
        if page and used+height>capacity:
            pages.append(page)
            page=[]
            used=0
            capacity=165.75
        # Input fields max 200 chars: wrapped rows fit a whole page.
        if height>capacity:
            raise ValueError('A bill row is too tall to print; shorten the product fields')
        page.append((row,cells,height))
        used+=height
    if page: pages.append(page)
    if not pages: pages=[[]]
    total=dec(d['total'])
    paid=dec(d.get('paid',0))
    previous=dec(d.get('previous_balance',0))
    current=previous+(dec(d.get('balance',total-paid)) if d.get('status')!='void' else 0)
    cash=sum((dec(p['amount']) for p in d.get('payments',[]) if p['method']=='cash'),Decimal(0))
    noncash=paid-cash
    notes=str(d.get('notes',''))
    note_lines=wrap(notes,regular,7.5,280)
    address_lines=wrap(d.get('customer_address',''),bold,8,330)
    name_lines=wrap(d.get('customer_name',''),bold,9,330)
    extra=[]
    if len(name_lines)>1: extra.append(('Customer name',d['customer_name']))
    if len(address_lines)>1: extra.append(('Customer address',d['customer_address']))
    if len(note_lines)>2: extra.append(('Remark',notes))
    running=Decimal(0)
    running_qty=Decimal(0)
    created=d['created_at']
    if isinstance(created,str): created=datetime.fromisoformat(created.replace('Z','+00:00'))
    date=created.strftime('%d/%m/%Y')
    for index,rows in enumerate(pages):
        final=index==len(pages)-1
        c.setLineWidth(.6)
        heading='ESTIMATE SANITARYWARE'
        text(WIDTH/2,39.75,heading,title,18,'center')
        # Draft/void visibility is mandatory even on a bill matching the sample.
        if d.get('status') in ('draft','void'):
            text(577.5,42,d['status'].upper(),bold,6,'right')
        for x in (25.5,577.5): line(x,46.5,x,406.95)
        for y in (46.5,80.25,94.5,283.2,406.95): line(25.5,y,577.5,y)
        line(403.5,46.5,403.5,80.25)
        for x in EDGES[1:-1]: line(x,80.25,x,283.2)
        text(29.25,59.75,'M/s. :',bold,8)
        text(66.75,59.75,name_lines[0],bold,9,max_width=330)
        text(66.75,74.25,address_lines[0],bold,8,max_width=330)
        text(435,60,'No.     :',title,9)
        text(473.25,60,str(d.get('print_number') or f"{d['id']:06d}"),title,9,max_width=100)
        text(435,72,'Date   :',title,9)
        text(473.25,72,date,title,9)
        headers=['Product Name','Brand','Pack','Grade','Colour','Quantity','Rate','Amount']
        for i,label in enumerate(headers): text((EDGES[i]+EDGES[i+1])/2,91.5,label,bold,8,'center')
        y=105.75
        if index:
            text(28,y,'B/F->',regular,8)
            text(576,y,amount(running),regular,8,'right')
            y+=9.75
        for row,cells,height in rows:
            for i,cell in enumerate(cells):
                align='left' if i==0 else ('right' if i>=5 else 'center')
                x=EDGES[i]+2 if i==0 else (EDGES[i+1]-1.5 if i>=5 else (EDGES[i]+EDGES[i+1])/2)
                for j,value in enumerate(cell): text(x,y+j*9.75,value,regular,8,align)
            running+=dec(row['amount'])
            running_qty+=dec(row['quantity'])
            y+=height
        line(354.75,283.2,354.75,406.95)
        line(501,283.2,501,406.95)
        for yy in (325.2,358.2,390.45): line(25.5,yy,354.75,yy)
        line(354.75,374.7,577.5,374.7)
        text(103.5,294.75,'Vehicle No.     :',bold,8)
        text(178.5,294.75,d.get('vehicle_no',''),regular,8,max_width=169)
        text(41.25,314.25,'Cash Rs:-',bold,8)
        text(91.5,314.25,amount(cash),regular,8,max_width=90)
        text(192,313.5,'Bill Amt Rs:-',bold,8)
        text(255,313.5,amount(noncash),regular,8,max_width=94)
        text(489.75,294.75,quantity(running_qty)+' : Total :',bold,8,'right',max_width=130)
        text(576,294.75,amount(running),bold,8,'right',max_width=72)
        text(30.75,340.2,'Rupees :-',bold,8)
        if final:
            for j,value in enumerate(wrap(rupees(total),regular,7.5,275)):
                text(79.5,340.2+j*9,value,regular,7.5)
        text(30.75,370.2,'Remark :',bold,8)
        if final:
            for j,value in enumerate(note_lines[:2]): text(77,370.2+j*9,value,regular,7.5)
            if len(note_lines)>2: text(77,388,'Full remark on attached details page',regular,6)
        if dec(d.get('returned',0)) or dec(d.get('refunded',0)):
            text(30.75,402,'Return credit: '+amount(d.get('returned',0))+' | Refunded: '+amount(d.get('refunded',0))+' | Net bill: '+amount(d.get('net_total',total)),regular,7,max_width=318)
        text(406.5,369.75,'Grand Total' if final else 'C/F to Next page',bold,8)
        if final: text(576,369.75,amount(total),bold,8,'right',max_width=72)
        text(360.75,387,'Previous Balance Rs.',bold,8)
        text(576,387,amount(previous),regular,8,'right',max_width=72)
        text(360.75,402,'Current Balance Rs.',bold,8)
        text(576,402,amount(current),bold,8,'right',max_width=72)
        if len(pages)>1 or extra: text(577.5,419,f'Page {index+1}',regular,6,'right')
        c.showPage()
    # Preserve long customer details / remarks rather than clipping them.
    if extra:
        y=35
        text(25.5,y,'ATTACHED BILL DETAILS',bold,12)
        y+=22
        for label,value in extra:
            for i,part in enumerate(wrap(label+': '+value,regular,9,540)):
                if y>395:
                    c.showPage()
                    y=35
                text(25.5,y,part,regular,9)
                y+=12
            y+=12
        c.showPage()
    c.save()
    return output.getvalue()
