"""Authentication integration tests against disposable PostgreSQL only."""
import time
import os
import pyotp
import pytest
from test_postgres import client,post,setup
from app.auth import encrypt,decrypt,hash_password,check_password,digest,make_recovery
from app.db import connect

pytestmark=pytest.mark.skipif(not os.getenv('TILESTOCK_TEST_DATABASE_URL'),reason='Disposable PostgreSQL required')

PASSWORD='New user password 123!'

def add_user(role='viewer',enabled=False):
    secret=pyotp.random_base32()
    with connect() as c:
        u=c.execute('INSERT INTO app_users(email,name,role,password_hash,totp_secret,mfa_enabled) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id',(role+'@example.test',role,role,hash_password(PASSWORD),encrypt(secret) if enabled else None,enabled)).fetchone()
    return u['id'],secret

def challenge(client,email='viewer@example.test',password=PASSWORD):
    r=client.post('/api/auth/login',json=dict(email=email,password=password))
    assert r.status_code==200,r.text
    return r.json()

def verify(client,ch,code,status=200):
    r=client.post('/api/auth/verify',json=dict(challenge=ch['challenge'],code=code))
    assert r.status_code==status,r.text
    return r

def test_password_hash_and_encryption(client):
    a,b=hash_password(PASSWORD),hash_password(PASSWORD)
    assert a!=b and check_password(PASSWORD,a) and not check_password('bad',a)
    value=encrypt('SECRET');assert 'SECRET' not in value and decrypt(value)=='SECRET'

def test_enrollment_requires_both_factors_and_recovery_one_use(client):
    uid,_=add_user()
    client.cookies.clear()
    assert client.get('/api/products').status_code==401
    ch=challenge(client)
    assert ch['mode']=='enroll' and client.get('/api/products').status_code==401
    enroll=client.post('/api/auth/enrollment',json={'challenge':ch['challenge']}).json()
    assert '<svg' in enroll['qr_svg'] and len(enroll['secret'])==32
    good=pyotp.TOTP(enroll['secret']).now()
    invalid=next(str(i).zfill(6) for i in range(10) if str(i).zfill(6) not in [pyotp.TOTP(enroll['secret']).at(time.time()+offset) for offset in [-30,0,30]])
    verify(client,ch,invalid,401)
    result=verify(client,ch,good).json()
    assert len(result['recovery_codes'])==10
    assert client.get('/api/products').status_code==200
    verify(client,ch,good,401)
    with connect() as c:
        u=c.execute('SELECT * FROM app_users WHERE id=%s',(uid,)).fetchone()
        assert u['mfa_enabled'] and u['totp_secret']!=enroll['secret']
        assert c.execute('SELECT count(*) n FROM recovery_codes WHERE user_id=%s',(uid,)).fetchone()['n']==10
    client.cookies.clear()
    ch=challenge(client);verify(client,ch,good,401)
    verify(client,ch,result['recovery_codes'][0])
    client.cookies.clear();ch=challenge(client)
    verify(client,ch,result['recovery_codes'][0],401)
    verify(client,ch,result['recovery_codes'][1])

def test_bad_codes_block_challenge_and_persist_attempts(client):
    uid,secret=add_user(enabled=True);client.cookies.clear();ch=challenge(client)
    invalid=next(str(i).zfill(6) for i in range(10) if str(i).zfill(6) not in [pyotp.TOTP(secret).at(time.time()+offset) for offset in [-30,0,30]])
    for _ in range(5):verify(client,ch,invalid,401)
    verify(client,ch,pyotp.TOTP(secret).now(),401)
    with connect() as c:assert c.execute('SELECT attempts FROM auth_challenges WHERE token_hash=%s',(digest(ch['challenge']),)).fetchone()['attempts']==5

def test_expired_challenge_and_sessions(client):
    uid,secret=add_user(enabled=True);client.cookies.clear();ch=challenge(client)
    with connect() as c:c.execute("UPDATE auth_challenges SET expires_at=now()-interval '1 second' WHERE user_id=%s",(uid,))
    verify(client,ch,pyotp.TOTP(secret).now(),401)
    ch=challenge(client);verify(client,ch,pyotp.TOTP(secret).now())
    with connect() as c:c.execute("UPDATE auth_sessions SET last_seen=now()-interval '31 minutes' WHERE user_id=%s",(uid,))
    assert client.get('/api/products').status_code==401

@pytest.mark.parametrize('role',['sales','stock','viewer'])
def test_roles_backend_enforced(client,role):
    batch,cust=setup(client);uid,secret=add_user(role,True)
    client.cookies.clear();verify(client,challenge(client,role+'@example.test'),pyotp.TOTP(secret).now())
    assert client.get('/api/users').status_code==403
    assert client.get('/api/audit').status_code==403
    assert client.get('/api/products').status_code==200
    assert client.get('/api/customers').status_code==(403 if role=='stock' else 200)
    assert client.post('/api/customers',json={'name':'A'}).status_code==(201 if role=='sales' else 403)
    from uuid import uuid4
    def adjust(delta,unit=None):
        body={'delta':delta,'reason':'Role test','request_key':str(uuid4())}
        if unit:body['unit']=unit
        return client.post(f'/api/batches/{batch}/adjust',json=body)
    assert adjust('1').status_code==(200 if role=='stock' else 403)
    assert adjust('-1').status_code==403
    assert adjust('1','piece').status_code==403
    assert client.post('/api/documents/999/void',json={}).status_code==403
    assert client.post('/api/documents/999/returns',json={}).status_code==403

def test_admin_create_disable_reset_and_last_owner(client):
    u=post(client,'/users',dict(email='staff@example.test',name='Staff',role='sales',password=PASSWORD),201)
    assert u['force_password_change'] and not u['mfa_enabled']
    me=client.get('/api/auth/me').json()['user']
    post(client,'/users/'+str(me['id']),dict(name=me['name'],role='viewer',active=True),409)
    post(client,'/users/'+str(u['id']),dict(name='Staff',role='viewer',active=False))
    ch=client.post('/api/auth/login',json=dict(email=u['email'],password=PASSWORD));assert ch.status_code==401
    post(client,f"/users/{u['id']}/password",{'password':'Replacement password 123!'})
    assert PASSWORD not in client.post('/api/users',json={'email':'bad','password':PASSWORD,'role':'wrong','name':'A'}).text

def test_role_update_revokes_existing_sessions(client):
    uid,secret=add_user('viewer',True)
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app,headers={'X-TileStock-Client':'local'}) as staff:
        verify(staff,challenge(staff),pyotp.TOTP(secret).now())
        assert staff.get('/api/products').status_code==200
        post(client,f'/users/{uid}',dict(name='Viewer',role='viewer',active=False))
        assert staff.get('/api/products').status_code==401

def test_forced_password_change_and_audit_actor(client):
    post(client,'/products',dict(sku='AUDIT',name='Audit Tile',sale_price='10'),201)
    with connect() as c:
        a=c.execute("SELECT actor_email FROM audit_log WHERE entity='products' AND action='INSERT' ORDER BY id DESC LIMIT 1").fetchone()
        assert a['actor_email']=='owner@example.test'
    uid,secret=add_user(enabled=True)
    with connect() as c:c.execute('UPDATE app_users SET force_password_change=true WHERE id=%s',(uid,))
    client.cookies.clear();verify(client,challenge(client),pyotp.TOTP(secret).now())
    assert client.get('/api/products').status_code==403
    r=client.post('/api/auth/password',json={'current_password':PASSWORD,'new_password':'Changed own password 123!'})
    assert r.status_code==200
    assert client.get('/api/auth/me').status_code==401
    with connect() as c:assert not c.execute('SELECT force_password_change FROM app_users WHERE id=%s',(uid,)).fetchone()['force_password_change']

def test_login_throttling_persists(client):
    client.cookies.clear()
    for _ in range(10):assert client.post('/api/auth/login',json={'email':'nobody@example.test','password':'wrong'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'nobody@example.test','password':'wrong'}).status_code==429

def test_authenticator_reset_requires_owner_reauthentication(client):
    uid,secret=add_user('viewer',True)
    with connect() as c:
        owner=c.execute("SELECT * FROM app_users WHERE email='owner@example.test'").fetchone()
        recovery=make_recovery(c,owner['id'])[0]
    r=client.post(f'/api/users/{uid}/authenticator-reset',json={'password':'wrong','code':recovery})
    assert r.status_code==401
    r=client.post(f'/api/users/{uid}/authenticator-reset',json={'password':'Test owner password 123!','code':recovery})
    assert r.status_code==200
    with connect() as c:
        u=c.execute('SELECT * FROM app_users WHERE id=%s',(uid,)).fetchone()
        assert not u['mfa_enabled'] and u['totp_secret'] is None
    client.cookies.clear();assert challenge(client)['mode']=='enroll'

def test_background_alert_poll_does_not_extend_session(client):
    with connect() as c:
        c.execute("UPDATE auth_sessions SET last_seen=now()-interval '5 minutes'")
        before=c.execute('SELECT last_seen FROM auth_sessions').fetchone()['last_seen']
    assert client.get('/api/stock-alerts',headers={'X-TileStock-Poll':'1'}).status_code==200
    with connect() as c:assert c.execute('SELECT last_seen FROM auth_sessions').fetchone()['last_seen']==before
    assert client.get('/api/auth/me').status_code==200
    with connect() as c:assert c.execute('SELECT last_seen FROM auth_sessions').fetchone()['last_seen']>before

def test_local_owner_bootstrap_and_recovery(client,monkeypatch):
    import owner_setup
    with connect() as c:c.execute('TRUNCATE app_users RESTART IDENTITY CASCADE')
    monkeypatch.setattr('sys.argv',['owner_setup.py'])
    answers=iter(['bootstrap@example.test','Owner'])
    monkeypatch.setattr('builtins.input',lambda prompt:next(answers))
    monkeypatch.setattr('getpass.getpass',lambda prompt:PASSWORD)
    owner_setup.run()
    with connect() as c:
        owner=c.execute('SELECT * FROM app_users').fetchone()
        assert owner['role']=='owner' and not owner['mfa_enabled'] and check_password(PASSWORD,owner['password_hash'])
        c.execute('UPDATE app_users SET active=false,mfa_enabled=true,totp_secret=%s WHERE id=%s',(encrypt(pyotp.random_base32()),owner['id']))
    monkeypatch.setattr('sys.argv',['owner_setup.py','--recover-owner'])
    monkeypatch.setattr('builtins.input',lambda prompt:'bootstrap@example.test')
    owner_setup.run()
    with connect() as c:
        owner=c.execute('SELECT * FROM app_users').fetchone()
        assert owner['active'] and not owner['mfa_enabled'] and owner['totp_secret'] is None
    monkeypatch.setattr('sys.argv',['owner_setup.py'])
    with pytest.raises(SystemExit):owner_setup.run()
