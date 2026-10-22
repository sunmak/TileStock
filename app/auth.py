"""Local email/password + mandatory TOTP, server sessions and role checks.
No authentication bypass or test-mode switch exists in the shipped application.
"""
import base64
import hashlib
import hmac
import io
import os
from pathlib import Path
import re
import secrets
import time
from datetime import datetime,timezone
from functools import lru_cache
from typing import Literal
from cryptography.fernet import Fernet,InvalidToken
import pyotp
import qrcode
import qrcode.image.svg
from fastapi import APIRouter,HTTPException,Request,Response
from pydantic import BaseModel,Field,field_validator
from .db import ROOT,connect,actor_context

router=APIRouter(prefix='/api')
COOKIE='shivam_session'
ROLES=('owner','sales','stock','viewer')

def digest(value):return hashlib.sha256(value.encode()).hexdigest()

def hash_password(password):
    salt=secrets.token_bytes(16)
    value=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000)
    return 'pbkdf2_sha256$600000$'+salt.hex()+'$'+value.hex()

def check_password(password,encoded):
    try:
        algorithm,rounds,salt,expected=encoded.split('$')
        if algorithm!='pbkdf2_sha256':return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(rounds)).hex()
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError):return False

DUMMY_HASH=hash_password('unused-'+secrets.token_hex(16))

def key_path():return Path(os.getenv('AUTH_KEY_FILE',str(ROOT/'.security'/'auth.key'))).resolve()

@lru_cache(maxsize=8)
def load_cipher(path):
    path=Path(path)
    if not path.exists():
        with connect() as c:
            if c.execute('SELECT 1 FROM app_users WHERE mfa_enabled LIMIT 1').fetchone():
                raise RuntimeError('Authenticator key missing. Restore .security/auth.key from your secure backup.')
        path.parent.mkdir(parents=True,exist_ok=True)
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(Fernet.generate_key())
        except FileExistsError:pass
    return Fernet(path.read_bytes().strip())

def encrypt(secret):return load_cipher(str(key_path())).encrypt(secret.encode()).decode()
def decrypt(secret):return load_cipher(str(key_path())).decrypt(secret.encode()).decode()

def audit(c,action,entity='',entity_id='',actor=None):
    actor=actor or actor_context.get()
    c.execute('INSERT INTO audit_log(actor_id,actor_email,action,entity,entity_id) VALUES (%s,%s,%s,%s,%s)',
      (actor['id'] if actor else None,actor['email'] if actor else 'local/setup',action,entity,str(entity_id)))

def public_user(user):return {k:user[k] for k in ('id','email','name','role','active','mfa_enabled','force_password_change')}

class Credentials(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=1,max_length=128)
    @field_validator('email')
    @classmethod
    def email_valid(cls,value):
        value=value.strip().lower()
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',value):raise ValueError('Enter a valid email address')
        return value

class Challenge(BaseModel):
    challenge:str=Field(min_length=40,max_length=100)

class Verification(Challenge):
    code:str=Field(min_length=6,max_length=64)

class NewUser(Credentials):
    name:str=Field(min_length=1,max_length=200)
    role:Literal['owner','sales','stock','viewer']
    @field_validator('password')
    @classmethod
    def long_password(cls,value):
        if len(value)<12:raise ValueError('Use at least 12 characters')
        return value

class UpdateUser(BaseModel):
    name:str=Field(min_length=1,max_length=200)
    role:Literal['owner','sales','stock','viewer']
    active:bool

class ResetPassword(BaseModel):
    password:str=Field(min_length=12,max_length=128)

class ChangePassword(BaseModel):
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=12,max_length=128)

class Reauthenticate(BaseModel):
    password:str=Field(min_length=1,max_length=128)
    code:str=Field(min_length=6,max_length=64)

def rate(c,key,limit,seconds=900):
    row=c.execute('''INSERT INTO auth_limits(key,count) VALUES (%s,1)
      ON CONFLICT(key) DO UPDATE SET count=CASE WHEN auth_limits.started_at<now()-%s*interval '1 second' THEN 1 ELSE auth_limits.count+1 END,
      started_at=CASE WHEN auth_limits.started_at<now()-%s*interval '1 second' THEN now() ELSE auth_limits.started_at END RETURNING count''',
      (key,seconds,seconds)).fetchone()
    return row['count']<=limit

def valid_code(c,user,code):
    """Must hold user row lock. A timestep or recovery code is consumed once."""
    normalized=code.strip().replace('-','').replace(' ','').upper()
    if re.fullmatch(r'\d{6}',normalized):
        try:totp=pyotp.TOTP(decrypt(user['totp_secret']))
        except (InvalidToken,ValueError):return False
        current=int(time.time()//30)
        for step in (current,current-1,current+1):
            if step>user['last_totp_step'] and hmac.compare_digest(totp.at(step*30),normalized):
                c.execute('UPDATE app_users SET last_totp_step=%s WHERE id=%s',(step,user['id']))
                return True
        return False
    row=c.execute('''UPDATE recovery_codes SET used_at=now() WHERE user_id=%s AND code_hash=%s
      AND used_at IS NULL RETURNING code_hash''',(user['id'],digest(normalized))).fetchone()
    return bool(row)

def make_recovery(c,user_id):
    codes=[secrets.token_hex(8).upper() for _ in range(10)]
    c.execute('DELETE FROM recovery_codes WHERE user_id=%s',(user_id,))
    for code in codes:c.execute('INSERT INTO recovery_codes(user_id,code_hash) VALUES (%s,%s)',(user_id,digest(code)))
    return ['-'.join(code[i:i+4] for i in range(0,16,4)) for code in codes]

def get_session(request):
    token=request.cookies.get(COOKIE)
    if not token or len(token)>100:return None
    with connect() as c:
        user=c.execute('''SELECT u.*,s.token_hash FROM auth_sessions s JOIN app_users u ON u.id=s.user_id
          WHERE s.token_hash=%s AND u.active AND u.mfa_enabled AND s.version=u.session_version
          AND s.expires_at>now() AND s.last_seen>now()-interval '30 minutes' ''',(digest(token),)).fetchone()
        if user and request.headers.get('x-tilestock-poll')!='1':c.execute("UPDATE auth_sessions SET last_seen=now() WHERE token_hash=%s AND last_seen<now()-interval '1 minute'",(digest(token),))
        return user

def access(request):
    path=request.url.path
    public={'/api/health','/api/auth/status','/api/auth/login','/api/auth/enrollment','/api/auth/verify'}
    if not path.startswith('/api/') or path in public:return None,None
    user=get_session(request)
    if not user:return None,(401,'Sign in with your email, password and authenticator code.')
    if user['force_password_change'] and path not in ('/api/auth/me','/api/auth/password','/api/auth/logout'):
        return user,(403,'Change your temporary password before continuing.')
    if path.startswith('/api/auth/'):return user,None
    if path.startswith('/api/users') or path in ('/api/audit','/api/corrections'):
        return (user,None) if user['role']=='owner' else (user,(403,'Owner access required'))
    if request.method=='GET':
        if user['role']=='stock' and (path.startswith('/api/documents') or path.startswith('/api/customers') or path.startswith('/api/returns')):
            return user,(403,'Your role does not have access to customer or sales records')
        return user,None
    role=user['role']
    if role=='owner':return user,None
    if role=='sales' and (re.fullmatch(r'/api/customers/\d+/edit',path) or path=='/api/customers' or path=='/api/documents' or re.fullmatch(r'/api/documents/\d+/(convert|post|payments)',path)):
        return user,None
    if role=='stock' and (path in ('/api/products','/api/batches') or re.fullmatch(r'/api/(products/\d+/(stock-policy|edit)|batches/\d+/adjust)',path)):
        return user,None
    return user,(403,'Your role does not permit this action')

def owner_only():
    actor=actor_context.get()
    if not actor or actor['role']!='owner':raise HTTPException(403,'Owner access required')
    return actor

@router.get('/auth/status')
def auth_status():
    with connect() as c:
        return {'setup_required':not bool(c.execute('SELECT 1 FROM app_users LIMIT 1').fetchone())}

@router.post('/auth/login')
def login(body:Credentials,request:Request):
    error=None;result=None
    with connect() as c:
        ip=request.client.host if request.client else 'local'
        allowed=rate(c,'login-ip:'+ip,60)&rate(c,'login-email:'+digest(body.email),10)
        if not allowed:error=(429,'Too many login attempts. Try again in 15 minutes.')
        else:
            user=c.execute('SELECT * FROM app_users WHERE email=%s FOR UPDATE',(body.email,)).fetchone()
            correct=check_password(body.password,user['password_hash'] if user else DUMMY_HASH)
            if not user or not user['active'] or not correct:
                audit(c,'LOGIN_PASSWORD_FAILED','authentication')
                error=(401,'Invalid email or password')
            else:
                token=secrets.token_urlsafe(32);mode='verify' if user['mfa_enabled'] else 'enroll'
                pending=encrypt(pyotp.random_base32()) if mode=='enroll' else None
                c.execute('UPDATE auth_challenges SET consumed=true,pending_secret=NULL WHERE user_id=%s',(user['id'],))
                c.execute("INSERT INTO auth_challenges(token_hash,user_id,version,mode,pending_secret,expires_at) VALUES (%s,%s,%s,%s,%s,now()+interval '5 minutes')",
                  (digest(token),user['id'],user['session_version'],mode,pending))
                result={'challenge':token,'mode':mode,'expires_in':300}
    if error:raise HTTPException(*error)
    return result

def challenge_user(c,token):
    meta=c.execute('SELECT user_id FROM auth_challenges WHERE token_hash=%s',(digest(token),)).fetchone()
    if not meta:return None,None
    user=c.execute('SELECT * FROM app_users WHERE id=%s FOR UPDATE',(meta['user_id'],)).fetchone()
    challenge=c.execute('SELECT *,expires_at>now() AS valid_time FROM auth_challenges WHERE token_hash=%s FOR UPDATE',(digest(token),)).fetchone()
    if not user or not user['active'] or not challenge or challenge['consumed'] or not challenge['valid_time'] or challenge['attempts']>=5 or challenge['version']!=user['session_version']:
        return None,None
    return user,challenge

@router.post('/auth/enrollment')
def enrollment(body:Challenge):
    with connect() as c:
        user,ch=challenge_user(c,body.challenge)
        if not user or ch['mode']!='enroll' or user['mfa_enabled']:raise HTTPException(401,'Start login again')
        secret=decrypt(ch['pending_secret'])
        uri=pyotp.TOTP(secret).provisioning_uri(name=user['email'],issuer_name='Shivam Tiles')
        image=qrcode.make(uri,image_factory=qrcode.image.svg.SvgPathImage)
        out=io.BytesIO();image.save(out)
        return {'secret':secret,'qr_svg':out.getvalue().decode(),'email':user['email']}

@router.post('/auth/verify')
def verify(body:Verification,request:Request,response:Response):
    error=None;result=None;session_token=None
    with connect() as c:
        ip=request.client.host if request.client else 'local'
        if not rate(c,'verify-ip:'+ip,60):error=(429,'Too many attempts. Try again in 15 minutes.')
        else:
            user,ch=challenge_user(c,body.challenge)
            if not user:error=(401,'Login expired or blocked. Start again.')
            else:
                c.execute('UPDATE auth_challenges SET attempts=attempts+1 WHERE token_hash=%s',(digest(body.challenge),))
                recovery=[]
                candidate=dict(user)
                if ch['mode']=='enroll':candidate['totp_secret']=ch['pending_secret']
                # Recovery is available only after authenticator enrollment.
                good=(bool(re.fullmatch(r'\d{6}',body.code.strip())) if ch['mode']=='enroll' else True) and valid_code(c,candidate,body.code)
                if not good:
                    audit(c,'LOGIN_SECOND_FACTOR_FAILED','app_users',user['id'],user)
                    error=(401,'Invalid or already-used code. Use a fresh code or an unused recovery code.')
                else:
                    if ch['mode']=='enroll':
                        c.execute('UPDATE app_users SET totp_secret=%s,mfa_enabled=true WHERE id=%s',(ch['pending_secret'],user['id']))
                        recovery=make_recovery(c,user['id']);user['mfa_enabled']=True
                    c.execute('UPDATE auth_challenges SET consumed=true,pending_secret=NULL WHERE token_hash=%s',(digest(body.challenge),))
                    session_token=secrets.token_urlsafe(32)
                    c.execute("INSERT INTO auth_sessions(token_hash,user_id,version,expires_at) VALUES (%s,%s,%s,now()+interval '8 hours')",(digest(session_token),user['id'],user['session_version']))
                    audit(c,'LOGIN_SUCCESS','app_users',user['id'],user)
                    result={'user':public_user(user),'recovery_codes':recovery}
    if error:raise HTTPException(*error)
    response.set_cookie(COOKIE,session_token,httponly=True,samesite='strict',secure=False,max_age=28800,path='/')
    response.headers['Cache-Control']='no-store'
    return result

@router.get('/auth/me')
def me():return {'user':public_user(actor_context.get())}

@router.post('/auth/logout')
def logout(request:Request,response:Response):
    with connect() as c:
        c.execute('DELETE FROM auth_sessions WHERE token_hash=%s',(digest(request.cookies.get(COOKIE,'')),))
        audit(c,'LOGOUT','app_users',actor_context.get()['id'])
    response.delete_cookie(COOKIE,path='/')
    return {'ok':True}

@router.post('/auth/password')
def change_password(body:ChangePassword,response:Response):
    actor=actor_context.get();error=None
    with connect() as c:
        user=c.execute('SELECT * FROM app_users WHERE id=%s FOR UPDATE',(actor['id'],)).fetchone()
        if not rate(c,'change-password:'+str(user['id']),5):error=(429,'Too many attempts. Try again later.')
        elif not check_password(body.current_password,user['password_hash']):error=(401,'Current password is incorrect')
        elif body.current_password==body.new_password:error=(422,'Choose a different new password')
        else:
            c.execute('UPDATE app_users SET password_hash=%s,force_password_change=false,session_version=session_version+1 WHERE id=%s',(hash_password(body.new_password),user['id']))
            c.execute('DELETE FROM auth_sessions WHERE user_id=%s',(user['id'],))
            audit(c,'PASSWORD_CHANGED','app_users',user['id'])
    if error:raise HTTPException(*error)
    response.delete_cookie(COOKIE,path='/');return {'ok':True,'login_required':True}

@router.post('/auth/recovery-codes')
def regenerate_codes(body:Reauthenticate):
    actor=actor_context.get();error=None;codes=[]
    with connect() as c:
        user=c.execute('SELECT * FROM app_users WHERE id=%s FOR UPDATE',(actor['id'],)).fetchone()
        if not rate(c,'recovery-refresh:'+str(user['id']),5):error=(429,'Too many attempts. Try again later.')
        elif not check_password(body.password,user['password_hash']) or not valid_code(c,user,body.code):error=(401,'Password or code is incorrect or already used')
        else:
            codes=make_recovery(c,user['id']);audit(c,'RECOVERY_CODES_REGENERATED','app_users',user['id'])
    if error:raise HTTPException(*error)
    return {'recovery_codes':codes}

@router.get('/users')
def users():
    owner_only()
    with connect() as c:return [public_user(row) for row in c.execute('SELECT * FROM app_users ORDER BY id').fetchall()]

@router.post('/users',status_code=201)
def create_user(body:NewUser):
    owner_only()
    with connect() as c:
        row=c.execute('''INSERT INTO app_users(email,name,role,password_hash,force_password_change)
          VALUES (%s,%s,%s,%s,true) RETURNING *''',(body.email,body.name.strip(),body.role,hash_password(body.password))).fetchone()
        audit(c,'USER_CREATED','app_users',row['id']);return public_user(row)

@router.post('/users/{user_id}')
def update_user(user_id:int,body:UpdateUser):
    actor=owner_only()
    with connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(72831949)')
        user=c.execute('SELECT * FROM app_users WHERE id=%s FOR UPDATE',(user_id,)).fetchone()
        if not user:raise HTTPException(404,'User not found')
        if user['role']=='owner' and user['active'] and (not body.active or body.role!='owner'):
            count=c.execute("SELECT count(*) n FROM app_users WHERE role='owner' AND active").fetchone()['n']
            if count<=1:raise HTTPException(409,'The last active owner cannot be disabled or demoted')
        if user_id==actor['id'] and (not body.active or body.role!='owner'):
            raise HTTPException(409,'Use another owner to change your own role or active status')
        row=c.execute('UPDATE app_users SET name=%s,role=%s,active=%s,session_version=session_version+1 WHERE id=%s RETURNING *',(body.name.strip(),body.role,body.active,user_id)).fetchone()
        c.execute('DELETE FROM auth_sessions WHERE user_id=%s',(user_id,))
        audit(c,'USER_ACCESS_UPDATED','app_users',user_id);return public_user(row)

@router.post('/users/{user_id}/password')
def reset_password(user_id:int,body:ResetPassword):
    actor=owner_only()
    if actor['id']==user_id:raise HTTPException(409,'Use Change password for your own account')
    with connect() as c:
        user=c.execute('UPDATE app_users SET password_hash=%s,force_password_change=true,session_version=session_version+1 WHERE id=%s RETURNING id',(hash_password(body.password),user_id)).fetchone()
        if not user:raise HTTPException(404,'User not found')
        c.execute('DELETE FROM auth_sessions WHERE user_id=%s',(user_id,))
        audit(c,'USER_PASSWORD_RESET','app_users',user_id)
    return {'ok':True}

@router.get('/audit')
def audit_history():
    owner_only()
    with connect() as c:return c.execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT 500').fetchall()

@router.post('/users/{user_id}/authenticator-reset')
def reset_authenticator(user_id:int,body:Reauthenticate):
    actor=owner_only()
    if actor['id']==user_id:raise HTTPException(409,'Use a recovery code to sign in, or the local owner recovery tool')
    error=None
    with connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(72831949)')
        owner=c.execute('SELECT * FROM app_users WHERE id=%s FOR UPDATE',(actor['id'],)).fetchone()
        if not rate(c,'mfa-reset:'+str(owner['id']),5):error=(429,'Too many attempts. Try again later.')
        elif not check_password(body.password,owner['password_hash']) or not valid_code(c,owner,body.code):error=(401,'Password or code is incorrect or already used')
        else:
            target=c.execute('''UPDATE app_users SET totp_secret=NULL,mfa_enabled=false,last_totp_step=-1,
              session_version=session_version+1 WHERE id=%s RETURNING id''',(user_id,)).fetchone()
            if not target:error=(404,'User not found')
            else:
                c.execute('DELETE FROM auth_sessions WHERE user_id=%s',(user_id,))
                c.execute('DELETE FROM recovery_codes WHERE user_id=%s',(user_id,))
                c.execute('UPDATE auth_challenges SET consumed=true,pending_secret=NULL WHERE user_id=%s',(user_id,))
                audit(c,'USER_AUTHENTICATOR_RESET','app_users',user_id)
    if error:raise HTTPException(*error)
    return {'ok':True,'enrollment_required':True}
