from app.invoice_pdf import rupees,wrap,fonts,render_bill
from reportlab.pdfbase import pdfmetrics
from datetime import datetime
from decimal import Decimal

def test_amount_in_words_and_paise():
    assert rupees('62620.00')=='Sixty Two Thousand Six Hundred Twenty Only'
    assert rupees('0.05')=='Zero And Five Paise Only'
    assert rupees('1000000.01')=='One Million And One Paise Only'

def test_long_field_wrap_preserves_text():
    font=fonts()[0]
    value='Very long tile name '+'A'*200
    lines=wrap(value,font,8,168)
    assert ''.join(''.join(lines).split())==''.join(value.split())
    assert all(pdfmetrics.stringWidth(x,font,8)<=168 for x in lines)

def test_multi_page_bill_and_large_notes():
    rows=[dict(product_name='Tile '+str(i),description='Tile',quantity=1,unit_price=1,amount=1,brand='Brand',pack='Pack',grade='A',colour='White') for i in range(40)]
    d=dict(id=1,kind='invoice',status='posted',customer_name='Customer',customer_address='Address',created_at=datetime(2026,10,22),total=Decimal(40),paid=0,lines=rows,payments=[],notes='Long remark '*300)
    result=render_bill(d)
    assert result.startswith(b'%PDF-')
    assert len(result)>1000

import pytest
@pytest.mark.parametrize('kind',['estimate','invoice'])
def test_exact_bill_heading_for_both_document_kinds(monkeypatch,kind):
    from reportlab.pdfgen.canvas import Canvas
    seen=[]
    original=Canvas.drawCentredString
    def capture(self,x,y,text,*args,**kwargs):
        seen.append(text)
        return original(self,x,y,text,*args,**kwargs)
    monkeypatch.setattr(Canvas,'drawCentredString',capture)
    d=dict(id=1,kind=kind,status='draft',customer_name='Customer',customer_address='',created_at=datetime(2026,10,22),total=Decimal(1),paid=0,lines=[dict(product_name='Tile',description='Tile',quantity=1,unit_price=1,amount=1)],payments=[],notes='')
    result=render_bill(d)
    assert result.startswith(b'%PDF-') and 'ESTIMATE SANITARYWARE' in seen
    assert 'INVOICE SANITARYWARE' not in seen
