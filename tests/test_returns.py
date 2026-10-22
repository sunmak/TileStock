from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4
from test_postgres import client,setup,post,draft,stock
import os,pytest

pytestmark=pytest.mark.skipif(not os.getenv('TILESTOCK_TEST_DATABASE_URL'),reason='Disposable test PostgreSQL required')

def sold(client,quantity='5',paid=None):
    b,c=setup(client)
    invoice=draft(client,b,c,qty=quantity)
    post(client,f'/documents/{invoice}/post')
    if paid:
        post(client,f'/documents/{invoice}/payments',dict(amount=paid,method='cash',request_key=str(uuid4())),201)
    d=client.get(f'/api/documents/{invoice}').json()
    return invoice,d['lines'][0]['id']

def returned(client,invoice,line,quantity='2',restock=True,key=None,status=201):
    return post(client,f'/documents/{invoice}/returns',dict(reason='Customer brought back goods',request_key=key or str(uuid4()),lines=[dict(document_line_id=line,quantity=quantity,restock=restock)]),status)

def value(client,invoice,field):
    return Decimal(str(client.get(f'/api/documents/{invoice}').json()[field]))

def test_partial_return_restocks_original_batch_and_reduces_due(client):
    invoice,line=sold(client)
    r=returned(client,invoice,line)
    assert stock(client)==7
    assert value(client,invoice,'returned')==20
    assert value(client,invoice,'due')==30
    detail=client.get(f"/api/returns/{r['id']}").json()
    assert detail['lines'][0]['restock'] is True
    assert client.get('/api/returns').json()[0]['id']==r['id']
    movement=client.get('/api/movements').json()[0]
    assert movement['return_id']==r['id']
    post(client,f'/documents/{invoice}/void',status=409)
    post(client,f'/documents/{invoice}/payments',dict(amount='31',method='cash',request_key=str(uuid4())),409)

def test_return_retry_and_excess_are_safe(client):
    invoice,line=sold(client)
    key=str(uuid4())
    first=returned(client,invoice,line,key=key)
    assert returned(client,invoice,line,key=key)==first
    assert stock(client)==7
    returned(client,invoice,line,quantity='3',key=key,status=409)
    returned(client,invoice,line,quantity='4',status=409)
    assert stock(client)==7
    returned(client,invoice,line,quantity='3')
    assert stock(client)==10
    assert value(client,invoice,'net_total')==0
    returned(client,invoice,line,quantity='0.001',status=409)

def test_damaged_return_credits_without_restocking(client):
    invoice,line=sold(client)
    returned(client,invoice,line,restock=False)
    assert stock(client)==5
    assert value(client,invoice,'returned')==20
    assert value(client,invoice,'balance')==30

def test_paid_return_credit_and_refund_retry_limit(client):
    invoice,line=sold(client,paid='50')
    returned(client,invoice,line)
    assert value(client,invoice,'balance')==-20
    assert value(client,invoice,'refund_due')==20
    body=dict(amount='10',method='cash',reference='Refund handed over',request_key=str(uuid4()))
    first=post(client,f'/documents/{invoice}/refunds',body,201)
    assert post(client,f'/documents/{invoice}/refunds',body,201)==first
    assert value(client,invoice,'refund_due')==10
    post(client,f'/documents/{invoice}/refunds',{**body,'amount':'11','request_key':str(uuid4())},409)
    assert stock(client)==7
    post(client,f'/documents/{invoice}/refunds',{**body,'request_key':str(uuid4())},201)
    assert value(client,invoice,'balance')==0
    assert value(client,invoice,'refunded')==20

def test_partly_paid_return_applies_to_debt_before_refund(client):
    invoice,line=sold(client,paid='20')
    returned(client,invoice,line,quantity='4')
    assert value(client,invoice,'net_total')==10
    assert value(client,invoice,'refund_due')==10
    assert value(client,invoice,'due')==0

def test_concurrent_returns_cannot_exceed_sale(client):
    invoice,line=sold(client)
    def receive(_):
        return client.post(f'/api/documents/{invoice}/returns',json=dict(reason='Return',request_key=str(uuid4()),lines=[dict(document_line_id=line,quantity='3',restock=True)])).status_code
    with ThreadPoolExecutor(2) as pool:
        codes=list(pool.map(receive,range(2)))
    assert sorted(codes)==[201,409]
    assert stock(client)==8
    assert value(client,invoice,'returned')==30

def test_concurrent_refunds_cannot_exceed_credit(client):
    invoice,line=sold(client,paid='50')
    returned(client,invoice,line)
    def refund(_):
        return client.post(f'/api/documents/{invoice}/refunds',json=dict(amount='15',method='cash',request_key=str(uuid4()))).status_code
    with ThreadPoolExecutor(2) as pool:
        codes=list(pool.map(refund,range(2)))
    assert sorted(codes)==[201,409]
    assert value(client,invoice,'refunded')==15

def test_bad_second_line_rolls_back_whole_return(client):
    invoice,line=sold(client)
    other,other_line=sold_another(client)
    post(client,f'/documents/{invoice}/returns',dict(reason='Return',request_key=str(uuid4()),lines=[dict(document_line_id=line,quantity='1'),dict(document_line_id=other_line,quantity='1')]),404)
    assert stock(client)==4  # first invoice sold 5; second sold 1
    assert value(client,invoice,'returned')==0
    assert client.get('/api/returns').json()==[]

def sold_another(client):
    invoice=draft(client,1,1,qty='1')
    post(client,f'/documents/{invoice}/post')
    return invoice,client.get(f'/api/documents/{invoice}').json()['lines'][0]['id']

def test_fractional_returns_credit_original_rounded_amount(client):
    b,c=setup(client)
    invoice=draft(client,b,c,lines=[dict(batch_id=b,quantity='0.015',unit_price='1')])
    post(client,f'/documents/{invoice}/post')
    line=client.get(f'/api/documents/{invoice}').json()['lines'][0]['id']
    for _ in range(3): returned(client,invoice,line,quantity='0.005')
    assert value(client,invoice,'returned')==Decimal('0.02')
    assert value(client,invoice,'net_total')==0
    assert stock(client)==10

def test_drafts_estimates_and_voids_reject_returns(client):
    b,c=setup(client)
    for kind in ('invoice','estimate'):
        invoice=draft(client,b,c,kind=kind)
        line=client.get(f'/api/documents/{invoice}').json()['lines'][0]['id']
        returned(client,invoice,line,status=409)
        post(client,f'/documents/{invoice}/void')
        returned(client,invoice,line,status=409)
