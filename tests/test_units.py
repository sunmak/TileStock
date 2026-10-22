from uuid import uuid4
import os,pytest
from test_postgres import client,post,setup,stock,draft

pytestmark=pytest.mark.skipif(not os.getenv('TILESTOCK_TEST_DATABASE_URL'),reason='Disposable PostgreSQL required')

def change(client,batch,unit='piece',delta='5',key=None,expected='box',status=200):
    return post(client,f'/batches/{batch}/adjust',dict(unit=unit,delta=delta,reason='Stock received',request_key=key or str(uuid4()),expected_stock_unit=expected),status)

def test_unit_changes_directly_without_conversion_and_retry_is_safe(client):
    batch,c=setup(client)
    key=str(uuid4());first=change(client,batch,key=key)
    assert stock(client)==15
    assert client.get('/api/products').json()[0]['unit']=='piece'
    assert change(client,batch,key=key)==first
    assert stock(client)==15
    movement=client.get('/api/movements').json()[0]
    assert movement['entered_quantity']==5 and movement['delta']==5
    assert movement['entered_unit']=='piece' and movement['stock_unit']=='piece'
    assert movement['conversion_factor']==1

def test_relabelling_preserves_other_batch_numbers_prices_thresholds_and_old_documents(client):
    batch,c=setup(client)
    invoice=draft(client,batch,c)
    other=post(client,'/batches',dict(product_id=1,code='Second'),201)
    post(client,'/products/1/stock-policy',dict(minimum_stock='20',critical_stock='3'))
    change(client,batch)
    batches=client.get('/api/batches').json()
    assert all(b['unit']=='piece' for b in batches)
    assert batches[1]['quantity']==0
    product=client.get('/api/products').json()[0]
    assert product['sale_price']==10 and product['minimum_stock']==20
    assert client.get(f'/api/documents/{invoice}').json()['lines'][0]['unit']=='box'

def test_failed_receipt_rolls_back_unit_change(client):
    batch,c=setup(client)
    change(client,batch,delta='-11',status=409)
    assert stock(client)==10
    assert client.get('/api/products').json()[0]['unit']=='box'

def test_stale_stock_unit_is_rejected(client):
    batch,c=setup(client)
    change(client,batch)
    change(client,batch,unit='carton',status=409)
    assert stock(client)==15
    assert client.get('/api/products').json()[0]['unit']=='piece'

def test_old_conversion_requests_rejected(client):
    batch,c=setup(client)
    post(client,f'/batches/{batch}/adjust',dict(delta='5',reason='Old client',request_key=str(uuid4()),conversion_id=1,expected_factor='4'),422)
    assert stock(client)==10
