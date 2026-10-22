"""Custom-format pg_dump, archive validation, optional synced-folder copy, keep two.
Cloud copy is filesystem delivery only: the sync provider must confirm upload.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime, timezone
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from app.db import ROOT, connect

PATTERN = re.compile(r'^tilestock_\d{8}T\d{12}Z\.dump$')

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.digest()

def prune(folder):
    # Only our timestamped direct-child dump files. Never traverse directories.
    files = sorted((p for p in folder.iterdir() if p.is_file() and not p.is_symlink() and PATTERN.fullmatch(p.name)), key=lambda p:p.name, reverse=True)
    for path in files[2:]:
        if path.resolve().parent != folder.resolve():
            raise RuntimeError('Unsafe backup path')
        path.unlink()

def run():
    folder = ROOT/'backups'
    folder.mkdir(exist_ok=True)
    cloud_value = os.getenv('CLOUD_BACKUP_DIR','').strip()
    cloud = Path(cloud_value).resolve() if cloud_value else None
    if cloud and (not cloud.is_dir() or cloud == folder.resolve()):
        raise RuntimeError('CLOUD_BACKUP_DIR must be an existing separate synced folder')
    pg_bin = os.getenv('PG_BIN','').strip()
    dump = str(Path(pg_bin)/'pg_dump.exe') if pg_bin else 'pg_dump'
    restore = str(Path(pg_bin)/'pg_restore.exe') if pg_bin else 'pg_restore'
    with connect() as conn:
        conn.execute('SELECT pg_advisory_lock(72831941)')
        config = conninfo_to_dict(os.environ['DATABASE_URL'])
        env = os.environ.copy()
        if 'password' in config:
            env['PGPASSWORD'] = config.pop('password')
        db_arg = make_conninfo(**config)
        filename = 'tilestock_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.dump'
        target = folder/filename
        partial = folder/(filename+'.partial')
        # Failed commands keep prior backups; incomplete files have .partial suffix.
        subprocess.run([dump,'--dbname',db_arg,'--format=custom','--no-owner','--no-privileges','--file',str(partial)], check=True, env=env)
        subprocess.run([restore,'--list',str(partial)], check=True, stdout=subprocess.DEVNULL, env=env)
        partial.replace(target)
        if cloud:
            cloud_partial = cloud/(filename+'.partial')
            shutil.copy2(target,cloud_partial)
            if digest(target) != digest(cloud_partial):
                raise RuntimeError('Backup copy checksum mismatch; older copies retained')
            cloud_partial.replace(cloud/filename)
        # Only rotate after dump validation AND configured filesystem copy succeed.
        prune(folder)
        if cloud:
            prune(cloud)
        print('Backup created:',target)
        print('User management: separately back up the matching .security/auth.key securely. It is NOT in this database dump.')
        print('Kept newest two local dumps and newest two in configured synced folder.' if cloud else 'Kept newest two local dumps. Cloud copy is not configured.')
        if cloud:
            print('Check Google Drive for desktop to confirm upload and deletion synchronization.')

if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('BACKUP FAILED:', type(exc).__name__, '— check database access, PG_BIN, disk space and synced-folder permissions.')
        raise SystemExit(1)
