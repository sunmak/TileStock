"""Trusted local-console bootstrap/recovery. Never reachable through the web UI."""
import argparse
import getpass
from app.db import connect,migrate
from app.auth import Credentials,hash_password,encrypt,audit

def run():
    parser=argparse.ArgumentParser()
    parser.add_argument('--recover-owner',action='store_true')
    args=parser.parse_args()
    migrate()
    email=input('Owner email address: ').strip().lower()
    Credentials(email=email,password='validation-only')
    with connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(72831949)')
        if not args.recover_owner and c.execute('SELECT 1 FROM app_users LIMIT 1').fetchone():
            raise SystemExit('Accounts already exist. Sign in as an owner to manage users. Use local recovery only if locked out.')
        password=getpass.getpass('New application password (12+ characters): ')
        if not 12<=len(password)<=128:raise SystemExit('Use a password between 12 and 128 characters.')
        if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match.')
        if args.recover_owner:
            user=c.execute("SELECT * FROM app_users WHERE email=%s AND role='owner' FOR UPDATE",(email,)).fetchone()
            if not user:raise SystemExit('No owner found with that email. No changes made.')
            c.execute('''UPDATE app_users SET password_hash=%s,active=true,mfa_enabled=false,totp_secret=NULL,
              last_totp_step=-1,force_password_change=false,session_version=session_version+1 WHERE id=%s''',(hash_password(password),user['id']))
            c.execute('DELETE FROM auth_sessions WHERE user_id=%s',(user['id'],))
            c.execute('DELETE FROM recovery_codes WHERE user_id=%s',(user['id'],))
            audit(c,'LOCAL_OWNER_RECOVERY','app_users',user['id'])
        else:
            # Create the encryption key before the owner is enrolled. No secret
            # or default password is shipped, logged or sent over the network.
            encrypt('key-readiness-check')
            name=input('Owner display name: ').strip() or 'Owner'
            user=c.execute("INSERT INTO app_users(email,name,role,password_hash) VALUES (%s,%s,'owner',%s) RETURNING id",(email,name,hash_password(password))).fetchone()
            audit(c,'LOCAL_OWNER_CREATED','app_users',user['id'])
    print('Owner account ready. Start the application, sign in, and scan its QR code in your authenticator app.')
    print('Keep .security/auth.key in a separate secure backup. Recovery codes are shown after enrollment.')

if __name__=='__main__':
    try:run()
    except Exception as exc:
        # No passwords, OTPs or connection strings in console diagnostics.
        print('Setup failed:',type(exc).__name__,'— check database setup and input. No password is logged.')
        raise SystemExit(1)
