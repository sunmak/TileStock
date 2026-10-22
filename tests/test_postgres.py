"""Real PostgreSQL tests. Explicit opt-in; ONLY use a disposable empty database.
Never point TILESTOCK_TEST_DATABASE_URL at your shop database.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

URL = os.getenv('TILESTOCK_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='Set TILESTOCK_TEST_DATABASE_URL to a disposable database')

@pytest.fixture
def client(monkeypatch,tmp_path):
    monkeypatch.setenv('DATABASE_URL', URL or '')
    monkeypatch.setenv('AUTH_KEY_FILE',str(tmp_path/'auth.key'))
    from app.db import connect
    from app.main import app
    with TestClient(app, headers={'X-TileStock-Client':'local'}) as client:
        with connect() as c:
            c.execute('TRUNCATE app_users,auth_limits,audit_log,products,customers,documents,batches,document_lines,stock_movements,payments,api_requests RESTART IDENTITY CASCADE')
        from app.auth import hash_password,encrypt
        import pyotp
        secret=pyotp.random_base32()
        with connect() as c:
            c.execute("INSERT INTO app_users(email,name,role,password_hash,totp_secret,mfa_enabled) VALUES ('owner@example.test','Test Owner','owner',%s,%s,true)",(hash_password('Test owner password 123!'),encrypt(secret)))
        challenge=client.post('/api/auth/login',json={'email':'owner@example.test','password':'Test owner password 123!'}).json()['challenge']
        response=client.post('/api/auth/verify',json={'challenge':challenge,'code':pyotp.TOTP(secret).now()})
        assert response.status_code==200,response.text
        yield client

def post(client,path,body=None,status=200):
    response=client.post('/api'+path,json=body or {})
    assert response.status_code==status, response.text
    return response.json()

def setup(client):
    p=post(client,'/products',dict(sku='T1',name='Tile',sale_price='10.00'),201)
    b=post(client,'/batches',dict(product_id=p['id'],code='B1'),201)
    c=post(client,'/customers',dict(name='Alice',address='Main Street'),201)
    post(client,f"/batches/{b['id']}/adjust",dict(delta='10',reason='Opening',request_key=str(uuid4())))
    return b['id'],c['id']

def draft(client,b,c,qty='3',kind='invoice',lines=None,key=None):
    return post(client,'/documents',dict(kind=kind,customer_id=c,notes='',request_key=key or str(uuid4()),lines=lines or [dict(batch_id=b,quantity=qty,unit_price='10.00')]),201)['id']

def stock(client):
    return Decimal(client.get('/api/batches').json()[0]['quantity'])

def test_estimate_conversion_post_retry_and_payment(client):
    b,c=setup(client)
    est=draft(client,b,c,kind='estimate')
    assert stock(client)==10
    invoice=post(client,f'/documents/{est}/convert')['id']
    assert post(client,f'/documents/{est}/convert')['id']==invoice
    assert stock(client)==10
    post(client,f'/documents/{invoice}/post')
    post(client,f'/documents/{invoice}/post')
    assert stock(client)==7
    payload=dict(amount='10',method='cash',reference='',request_key=str(uuid4()))
    first=post(client,f'/documents/{invoice}/payments',payload,201)
    assert post(client,f'/documents/{invoice}/payments',payload,201)==first
    post(client,f'/documents/{invoice}/payments',{**payload,'amount':'11'},409)
    post(client,f'/documents/{invoice}/payments',{**payload,'amount':'21','request_key':str(uuid4())},409)
    post(client,f'/documents/{invoice}/void',status=409)
    assert stock(client)==7
    assert Decimal(client.get(f'/api/documents/{invoice}').json()['balance'])==20

def test_multiline_failure_rolls_back_everything(client):
    b,c=setup(client)
    second=post(client,'/batches',dict(product_id=1,code='Empty'),201)['id']
    inv=draft(client,b,c,lines=[dict(batch_id=b,quantity='2',unit_price='10'),dict(batch_id=second,quantity='1',unit_price='10')])
    post(client,f'/documents/{inv}/post',status=409)
    assert stock(client)==10
    assert client.get(f'/api/documents/{inv}').json()['status']=='draft'
    assert len(client.get('/api/movements').json())==1

def test_void_restores_once_and_cannot_repost(client):
    b,c=setup(client)
    inv=draft(client,b,c)
    post(client,f'/documents/{inv}/post')
    post(client,f'/documents/{inv}/void')
    post(client,f'/documents/{inv}/void')
    post(client,f'/documents/{inv}/post',status=409)
    assert stock(client)==10
    assert len(client.get('/api/movements').json())==3

def test_concurrent_sales_cannot_oversell(client):
    b,c=setup(client)
    ids=[draft(client,b,c,qty='7') for _ in range(2)]
    with ThreadPoolExecutor(2) as pool:
        codes=list(pool.map(lambda i:client.post(f'/api/documents/{i}/post',json={}).status_code,ids))
    assert sorted(codes)==[200,409]
    assert stock(client)==3

def test_concurrent_payments_cannot_overpay(client):
    b,c=setup(client)
    inv=draft(client,b,c)
    post(client,f'/documents/{inv}/post')
    with ThreadPoolExecutor(2) as pool:
        codes=list(pool.map(lambda _:client.post(f'/api/documents/{inv}/payments',json=dict(amount='20',method='cash',request_key=str(uuid4()))).status_code,range(2)))
    assert sorted(codes)==[201,409]
    assert Decimal(client.get(f'/api/documents/{inv}').json()['balance'])==10

def test_adjustment_and_document_retries(client):
    b,c=setup(client)
    payload=dict(delta='2',reason='Delivery',request_key=str(uuid4()))
    first=post(client,f'/batches/{b}/adjust',payload)
    assert post(client,f'/batches/{b}/adjust',payload)==first
    assert stock(client)==12
    post(client,f'/batches/{b}/adjust',{**payload,'delta':'3'},409)
    post(client,f'/batches/{b}/adjust',dict(delta='-13',reason='Damage',request_key=str(uuid4())),409)
    key=str(uuid4())
    assert draft(client,b,c,key=key)==draft(client,b,c,key=key)

def test_decimal_totals_and_request_guard(client):
    b,c=setup(client)
    inv=draft(client,b,c,lines=[dict(batch_id=b,quantity='1.005',unit_price='1')])
    assert Decimal(str(client.get(f'/api/documents/{inv}').json()['total']))==Decimal('1.01')
    assert client.post('/api/customers',json={'name':'Mallory'},headers={'Origin':'https://example.com'}).status_code==403
    assert client.get('/api/health',headers={'Host':'evil.example'}).status_code==400

def test_migration_is_repeatable(client):
    from app.db import migrate,connect
    migrate()
    migrate()
    with connect() as c:
        assert c.execute('SELECT count(*) n FROM schema_migrations').fetchone()['n']==7

def test_bill_snapshots_vehicle_conversion_and_pdf(client):
    p=post(client,'/products',dict(sku='BILL',name='Wash Basin',sale_price='165',brand='SKYART',pack='PEPAR',grade='UTI'),201)
    b=post(client,'/batches',dict(product_id=p['id'],code='LOT',colour='WHITE'),201)
    customer=post(client,'/customers',dict(name='SHIVAM TILES',address='SIHOR'),201)
    e=post(client,'/documents',dict(kind='estimate',customer_id=customer['id'],vehicle_no='GJ13AX3454',request_key=str(uuid4()),lines=[dict(batch_id=b['id'],quantity='3',unit_price='165')]),201)['id']
    invoice=post(client,f'/documents/{e}/convert')['id']
    d=client.get(f'/api/documents/{invoice}').json()
    assert d['vehicle_no']=='GJ13AX3454'
    assert {k:d['lines'][0][k] for k in ('product_name','brand','pack','grade','colour')}==dict(product_name='Wash Basin',brand='SKYART',pack='PEPAR',grade='UTI',colour='WHITE')
    pdf=client.get(f'/api/documents/{invoice}/pdf')
    assert pdf.status_code==200
    assert pdf.headers['content-type']=='application/pdf'
    assert pdf.content.startswith(b'%PDF-')
