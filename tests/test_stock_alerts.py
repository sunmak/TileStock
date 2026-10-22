import os
from decimal import Decimal
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.stock_alerts import classify
from app.models import StockPolicy
from test_postgres import client,setup,post,draft

@pytest.mark.parametrize('quantity,minimum,critical,priority,enabled,expected',[
    ('0','10','3','low',True,'out_of_stock'),
    ('0','0','0','high',True,'out_of_stock'),
    ('0','10','3','high',False,'disabled'),
    ('3','10','3','low',True,'critical'),
    ('2.999','10','3','medium',True,'critical'),
    ('3.001','10','3','medium',True,'warning'),
    ('10','10','3','high',True,'critical'),
    ('10','10','3','medium',True,'warning'),
    ('10','10','3','low',True,'notice'),
    ('10.001','10','3','high',True,'healthy'),
    ('0.001','0','0','medium',True,'healthy'),
])
def test_severity_boundaries(quantity,minimum,critical,priority,enabled,expected):
    assert classify(Decimal(quantity),Decimal(minimum),Decimal(critical),priority,enabled)==expected

@pytest.mark.parametrize('body',[
    dict(minimum_stock='-1'),dict(minimum_stock='NaN'),dict(minimum_stock='1.0001'),
    dict(minimum_stock='5',critical_stock='6'),dict(criticality='urgent')])
def test_policy_validation(body):
    with pytest.raises(ValidationError):StockPolicy(**body)

db_test=pytest.mark.skipif(not os.getenv('TILESTOCK_TEST_DATABASE_URL'),reason='Disposable test database required')

def policy(client,id=1,**values):
    return post(client,f'/products/{id}/stock-policy',dict(criticality='medium',minimum_stock='8',critical_stock='3',stock_alerts_enabled=True,**values))

def alert(client,id=1):
    data=client.get('/api/stock-alerts').json()
    return next(p for p in data['products'] if p['id']==id)

@db_test
def test_batch_totals_and_policy_edit_preserve_catalogue_and_stock(client):
    b,c=setup(client)
    before=client.get('/api/products').json()[0]
    policy(client)
    second=post(client,'/batches',dict(product_id=1,code='Second'),201)['id']
    post(client,f'/batches/{second}/adjust',dict(delta='2',reason='Receipt',request_key=str(uuid4())))
    assert alert(client)['available']==12
    assert alert(client)['severity']=='healthy'
    after=client.get('/api/products').json()[0]
    assert all(after[k]==before[k] for k in ('sku','name','sale_price','unit','brand','pack','grade'))
    body=dict(minimum_stock='2',critical_stock='3')
    post(client,'/products/1/stock-policy',body,422)
    assert alert(client)['minimum_stock']==8
    post(client,'/products/9999/stock-policy',{},404)

@db_test
def test_alerts_change_after_sales_returns_receipts_and_adjustments(client):
    b,c=setup(client)
    policy(client)
    invoice=draft(client,b,c,qty='7')
    assert alert(client)['severity']=='healthy'  # draft doesn't deduct
    post(client,f'/documents/{invoice}/post')
    assert alert(client)['severity']=='critical'
    d=client.get(f'/api/documents/{invoice}').json()
    post(client,f'/documents/{invoice}/returns',dict(reason='Returned boxes',request_key=str(uuid4()),lines=[dict(document_line_id=d['lines'][0]['id'],quantity='2',restock=True)]),201)
    assert alert(client)['available']==5
    assert alert(client)['severity']=='warning'
    post(client,f'/documents/{invoice}/returns',dict(reason='Damaged box',request_key=str(uuid4()),lines=[dict(document_line_id=d['lines'][0]['id'],quantity='1',restock=False)]),201)
    assert alert(client)['available']==5
    post(client,f'/batches/{b}/adjust',dict(delta='5',reason='Delivery received',request_key=str(uuid4())))
    assert alert(client)['severity']=='healthy'
    post(client,f'/batches/{b}/adjust',dict(delta='-10',reason='Stock correction',request_key=str(uuid4())))
    assert alert(client)['severity']=='out_of_stock'

@db_test
def test_low_stock_clears_when_invoice_voided(client):
    b,c=setup(client)
    policy(client)
    invoice=draft(client,b,c,qty='8')
    post(client,f'/documents/{invoice}/post')
    assert alert(client)['severity']=='critical'
    post(client,f'/documents/{invoice}/void')
    assert alert(client)['severity']=='healthy'

@db_test
def test_no_batch_is_zero_and_disabled_products_do_not_alert(client):
    product=post(client,'/products',dict(sku='EMPTY',name='No batch yet',sale_price='10'),201)
    data=client.get('/api/stock-alerts').json()
    assert data['summary']['out_of_stock']==1
    assert data['alerts'][0]['available']==0
    post(client,f"/products/{product['id']}/stock-policy",dict(stock_alerts_enabled=False))
    data=client.get('/api/stock-alerts').json()
    assert data['summary']['total']==0 and data['summary']['monitored']==0
    assert data['products'][0]['severity']=='disabled'

@db_test
def test_urgency_sorting_and_product_creation_policy(client):
    # Deliberately create notice first and out-of-stock last to test actual ordering.
    entries=[('Low','low','5'),('Medium','medium','5'),('High','high','5'),('Empty','low','0')]
    ids={}
    for name,importance,amount in entries:
        p=post(client,'/products',dict(sku=name,name=name,sale_price='10',criticality=importance,minimum_stock='10',critical_stock='2'),201)
        ids[name]=p['id']
        b=post(client,'/batches',dict(product_id=p['id'],code='Batch'),201)
        if amount!='0':post(client,f"/batches/{b['id']}/adjust",dict(delta=amount,reason='Opening',request_key=str(uuid4())))
    data=client.get('/api/stock-alerts').json()
    assert [p['name'] for p in data['alerts']]==['Empty','High','Medium','Low']
    assert data['summary']==dict(out_of_stock=1,critical=1,warning=1,notice=1,total=4,monitored=4)
    assert data['alerts'][1]['criticality']=='high'

@db_test
def test_same_urgency_uses_criticality_then_coverage(client):
    for name,importance,quantity in [('Medium','medium','1'),('High more','high','3'),('High less','high','2')]:
        p=post(client,'/products',dict(sku=name,name=name,sale_price='1',criticality=importance,minimum_stock='10',critical_stock='3'),201)
        b=post(client,'/batches',dict(product_id=p['id'],code='Batch'),201)
        post(client,f"/batches/{b['id']}/adjust",dict(delta=quantity,reason='Opening',request_key=str(uuid4())))
    assert [p['name'] for p in client.get('/api/stock-alerts').json()['alerts']]==['High less','High more','Medium']
