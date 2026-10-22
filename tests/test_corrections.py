"""Editing and reversal invariants; disposable PostgreSQL only."""
import os
from uuid import uuid4
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_postgres import client,post,setup,draft,stock
from test_returns import sold,returned,value

pytestmark=pytest.mark.skipif(not os.getenv('TILESTOCK_TEST_DATABASE_URL'),reason='Disposable PostgreSQL required')

def correction(client,path,reason='Correct mistaken entry',key=None,status=200):
    return post(client,path,dict(reason=reason,request_key=key or str(uuid4())),status)

def edit_body(row,**changes):
    return {**row,'expected_version':row['version'],'reason':'Correct master details','request_key':str(uuid4()),**changes}

def test_master_edits_preserve_stock_and_saved_documents(client):
    b,c=setup(client);inv=draft(client,b,c)
    before=client.get(f'/api/documents/{inv}').json()
    product=client.get('/api/products').json()[0];customer=client.get('/api/customers').json()[0]
    pbody=edit_body(product,name='New tile name',sale_price='12.50',sku='NEW-SKU')
    first=post(client,f"/products/{product['id']}/edit",pbody)
    assert post(client,f"/products/{product['id']}/edit",pbody)==first
    post(client,f'/customers/{c}/edit',edit_body(customer,name='Updated customer',phone='9876543210',address='New Address'))
    after=client.get(f'/api/documents/{inv}').json()
    assert after['lines']==before['lines'] and after['customer_name']=='Alice'
    assert after['customer_address']==before['customer_address'] and stock(client)==10
    assert client.get('/api/customers/search?q=987654').json()['items'][0]['id']==c
    log=client.get('/api/corrections').json()
    assert len(log)==2 and log[0]['actor_email']=='owner@example.test'
    from app.db import connect
    with connect() as conn:
        saved=conn.execute("SELECT * FROM correction_log WHERE action='PRODUCT_EDITED'").fetchone()
        assert saved['before_data']['name']=='Tile' and saved['after_data']['name']=='New tile name'

def test_master_stale_unit_duplicate_and_missing_reason_are_safe(client):
    b,c=setup(client);p=client.get('/api/products').json()[0]
    post(client,f"/products/{p['id']}/edit",edit_body(p,unit='piece'),409)
    post(client,f"/products/{p['id']}/edit",edit_body(p,reason='   '),422)
    body=edit_body(p,name='New');post(client,f"/products/{p['id']}/edit",body)
    post(client,f"/products/{p['id']}/edit",edit_body(p,name='Stale'),409)
    other=post(client,'/products',dict(sku='OTHER',name='Other',sale_price='1'),201)
    current=next(x for x in client.get('/api/products').json() if x['id']==p['id'])
    post(client,f"/products/{p['id']}/edit",edit_body(current,sku='OTHER'),409)
    assert next(x for x in client.get('/api/products').json() if x['id']==p['id'])['name']=='New'
    assert stock(client)==10

def draft_edit_body(d,**changes):
    return dict(kind=d['kind'],customer_id=d['customer_id'],notes='Corrected notes',vehicle_no='TEST-123',lines=[dict(batch_id=l['batch_id'],quantity='4',unit_price='12.50') for l in d['lines']],expected_version=d['version'],reason='Owner checked quantities',request_key=str(uuid4()),**changes)

def test_draft_edit_preserves_number_no_stock_change_and_posts_new_lines(client):
    b,c=setup(client);inv=draft(client,b,c);d=client.get(f'/api/documents/{inv}').json()
    body=draft_edit_body(d);first=post(client,f'/documents/{inv}/edit',body)
    assert post(client,f'/documents/{inv}/edit',body)==first
    assert stock(client)==10
    new=client.get(f'/api/documents/{inv}').json();assert new['id']==inv and new['total']==50 and new['notes']=='Corrected notes'
    assert new['lines'][0]['quantity']==4 and new['vehicle_no']=='TEST-123'
    post(client,f'/documents/{inv}/edit',draft_edit_body(d),409)
    post(client,f'/documents/{inv}/post');assert stock(client)==6
    posted=client.get(f'/api/documents/{inv}').json()
    post(client,f'/documents/{inv}/edit',draft_edit_body(posted),409)

def test_draft_edit_customer_and_invalid_line_rollback(client):
    b,c=setup(client);inv=draft(client,b,c);d=client.get(f'/api/documents/{inv}').json()
    customer=post(client,'/customers',dict(name='Different customer',address='Other Street'),201)
    body=draft_edit_body(d);body['customer_id']=customer['id'];body['lines'][0]['batch_id']=999999
    post(client,f'/documents/{inv}/edit',body,404)
    unchanged=client.get(f'/api/documents/{inv}').json();assert unchanged==d
    body['request_key']=str(uuid4());body['lines'][0]['batch_id']=b
    post(client,f'/documents/{inv}/edit',body)
    changed=client.get(f'/api/documents/{inv}').json();assert changed['customer_name']=='Different customer' and changed['customer_address']=='Other Street'
    assert stock(client)==10

def test_converted_estimate_locked_but_linked_invoice_editable(client):
    b,c=setup(client);est=draft(client,b,c,kind='estimate');inv=post(client,f'/documents/{est}/convert')['id']
    e=client.get(f'/api/documents/{est}').json();post(client,f'/documents/{est}/edit',draft_edit_body(e),409)
    d=client.get(f'/api/documents/{inv}').json();post(client,f'/documents/{inv}/edit',draft_edit_body(d))

def test_two_draft_editors_cannot_overwrite_each_other(client):
    b,c=setup(client);inv=draft(client,b,c);d=client.get(f'/api/documents/{inv}').json()
    def edit(_):return client.post(f'/api/documents/{inv}/edit',json=draft_edit_body(d)).status_code
    with ThreadPoolExecutor(2) as pool:codes=list(pool.map(edit,range(2)))
    assert sorted(codes)==[200,409]
    assert len(client.get('/api/corrections').json())==1 and stock(client)==10

def test_return_reversal_undoes_stock_credit_and_allows_correct_reentry(client):
    inv,line=sold(client);r=returned(client,inv,line);key=str(uuid4())
    first=correction(client,f"/returns/{r['id']}/reverse",key=key)
    assert correction(client,f"/returns/{r['id']}/reverse",key=key)==first
    correction(client,f"/returns/{r['id']}/reverse")
    assert stock(client)==5 and value(client,inv,'returned')==0 and value(client,inv,'due')==50
    detail=client.get(f"/api/returns/{r['id']}").json()
    assert detail['reversed_at'] and detail['reversal_reason']=='Correct mistaken entry' and detail['total']==20
    assert client.get(f'/api/documents/{inv}').json()['lines'][0]['returnable_quantity']==5
    returned(client,inv,line,quantity='1');assert stock(client)==6 and value(client,inv,'returned')==10
    assert len(client.get('/api/movements').json())==5

def test_damaged_return_reversal_does_not_move_stock(client):
    inv,line=sold(client);r=returned(client,inv,line,restock=False)
    correction(client,f"/returns/{r['id']}/reverse")
    assert stock(client)==5 and value(client,inv,'due')==50

def test_refund_reversal_first_then_return_reversal(client):
    inv,line=sold(client,paid='50');r=returned(client,inv,line)
    f=post(client,f'/documents/{inv}/refunds',dict(amount='20',method='cash',request_key=str(uuid4())),201)
    correction(client,f"/returns/{r['id']}/reverse",status=409)
    assert stock(client)==7 and value(client,inv,'refunded')==20
    key=str(uuid4());correction(client,f"/refunds/{f['id']}/reverse",key=key)
    correction(client,f"/refunds/{f['id']}/reverse",key=key)
    assert value(client,inv,'refunded')==0 and value(client,inv,'refund_due')==20 and stock(client)==7
    correction(client,f"/returns/{r['id']}/reverse")
    assert value(client,inv,'balance')==0 and stock(client)==5
    assert client.get(f'/api/documents/{inv}').json()['refunds'][0]['reversed_at']

def test_reversal_stock_shortage_rolls_back_every_line(client):
    b,c=setup(client)
    p=post(client,'/products',dict(sku='SECOND',name='Second',sale_price='10'),201)
    b2=post(client,'/batches',dict(product_id=p['id'],code='B2'),201)['id']
    post(client,f'/batches/{b2}/adjust',dict(delta='10',reason='Receipt',request_key=str(uuid4())))
    inv=draft(client,b,c,lines=[dict(batch_id=i,quantity='5',unit_price='10') for i in [b,b2]])
    post(client,f'/documents/{inv}/post');d=client.get(f'/api/documents/{inv}').json()
    r=post(client,f'/documents/{inv}/returns',dict(reason='Return',request_key=str(uuid4()),lines=[dict(document_line_id=l['id'],quantity='2',restock=True) for l in d['lines']]),201)
    post(client,f'/batches/{b2}/adjust',dict(delta='-6',reason='Damaged',request_key=str(uuid4())))
    before=client.get('/api/batches').json();moves=client.get('/api/movements').json()
    correction(client,f"/returns/{r['id']}/reverse",status=409)
    assert client.get('/api/batches').json()==before and client.get('/api/movements').json()==moves
    assert not client.get(f"/api/returns/{r['id']}").json()['reversed_at']
    assert value(client,inv,'returned')==40

def test_fractional_returns_reverse_newest_first_preserves_rounding(client):
    b,c=setup(client);inv=draft(client,b,c,lines=[dict(batch_id=b,quantity='0.003',unit_price='5')]);post(client,f'/documents/{inv}/post')
    line=client.get(f'/api/documents/{inv}').json()['lines'][0]['id']
    returns=[returned(client,inv,line,quantity='0.001') for _ in range(3)]
    assert value(client,inv,'returned')==Decimal('.02')
    correction(client,f"/returns/{returns[0]['id']}/reverse",status=409)
    for r in reversed(returns):correction(client,f"/returns/{r['id']}/reverse")
    assert value(client,inv,'returned')==0
    returned(client,inv,line,quantity='0.003');assert value(client,inv,'returned')==Decimal('.02')

def test_concurrent_reversal_does_not_double_subtract_stock(client):
    inv,line=sold(client);r=returned(client,inv,line)
    def reverse(_):return client.post(f"/api/returns/{r['id']}/reverse",json=dict(reason='Concurrent fix',request_key=str(uuid4()))).status_code
    with ThreadPoolExecutor(2) as pool:codes=list(pool.map(reverse,range(2)))
    assert codes==[200,200] and stock(client)==5
    assert len(client.get('/api/corrections').json())==1

@pytest.mark.parametrize('role',['sales','stock','viewer'])
def test_corrections_owner_only_and_master_role_limits(client,role):
    from test_auth import add_user,challenge,verify
    import pyotp
    b,c=setup(client);inv=draft(client,b,c);d=client.get(f'/api/documents/{inv}').json()
    p=client.get('/api/products').json()[0];customer=client.get('/api/customers').json()[0]
    uid,secret=add_user(role,True);client.cookies.clear();verify(client,challenge(client,role+'@example.test'),pyotp.TOTP(secret).now())
    assert client.post(f'/api/documents/{inv}/edit',json=draft_edit_body(d)).status_code==403
    assert client.post('/api/returns/999/reverse',json=dict(reason='Fix',request_key=str(uuid4()))).status_code==403
    assert client.post('/api/refunds/999/reverse',json=dict(reason='Fix',request_key=str(uuid4()))).status_code==403
    assert client.get('/api/corrections').status_code==403
    assert client.post(f"/api/products/{p['id']}/edit",json=edit_body(p,name='Edited')).status_code==(200 if role=='stock' else 403)
    assert client.post(f'/api/customers/{c}/edit',json=edit_body(customer,name='Edited')).status_code==(200 if role=='sales' else 403)

def test_reversal_requires_reason_and_preserves_original_records(client):
    inv,line=sold(client);r=returned(client,inv,line)
    correction(client,f"/returns/{r['id']}/reverse",reason=' ',status=422)
    assert stock(client)==7
    correction(client,f"/returns/{r['id']}/reverse")
    doc=client.get(f'/api/documents/{inv}').json();assert len(doc['returns'])==1 and doc['returns'][0]['total']==20
    corrections=client.get('/api/corrections').json();assert corrections[0]['reason']=='Correct mistaken entry' and corrections[0]['entity_id']==r['id']
    # All returned goods have been undone, so an otherwise unpaid invoice may now be voided safely.
    post(client,f'/documents/{inv}/void');assert stock(client)==10

def test_edit_and_post_race_uses_one_complete_draft_version(client):
    b,c=setup(client);inv=draft(client,b,c);d=client.get(f'/api/documents/{inv}').json()
    def action(which):
        return client.post(f'/api/documents/{inv}/'+('edit' if which==0 else 'post'),json=draft_edit_body(d) if which==0 else {}).status_code
    with ThreadPoolExecutor(2) as pool:codes=list(pool.map(action,[0,1]))
    assert codes[1]==200 and codes[0] in [200,409]
    final=client.get(f'/api/documents/{inv}').json()
    assert final['status']=='posted' and stock(client)==10-Decimal(str(final['lines'][0]['quantity']))
    assert final['total']==(50 if codes[0]==200 else 30)

def test_corrected_refund_can_be_recorded_without_changing_stock(client):
    inv,line=sold(client,paid='50');returned(client,inv,line)
    old=post(client,f'/documents/{inv}/refunds',dict(amount='15',method='cash',request_key=str(uuid4())),201)
    correction(client,f"/refunds/{old['id']}/reverse")
    post(client,f'/documents/{inv}/refunds',dict(amount='20',method='upi',reference='Correct method',request_key=str(uuid4())),201)
    assert stock(client)==7 and value(client,inv,'refunded')==20 and value(client,inv,'balance')==0
    doc=client.get(f'/api/documents/{inv}').json();assert len(doc['refunds'])==2 and doc['refunds'][0]['reversed_at'] and not doc['refunds'][1]['reversed_at']
