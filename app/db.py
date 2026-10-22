import os
from contextvars import ContextVar
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
actor_context = ContextVar('actor', default=None)

def connect():
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('DATABASE_URL is missing. Copy .env.example to .env and edit it.')
    actor=actor_context.get()
    options='-c lock_timeout=10000 -c statement_timeout=30000'
    if actor:options+=' -c app.actor_id='+str(int(actor['id']))
    return psycopg.connect(url,row_factory=dict_row,connect_timeout=5,options=options)

def migrate():
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(72831940)')
        conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
        for path in sorted((ROOT / 'migrations').glob('*.sql')):
            if not conn.execute('SELECT 1 FROM schema_migrations WHERE name=%s', (path.name,)).fetchone():
                conn.execute(path.read_text(encoding='utf-8'))
                conn.execute('INSERT INTO schema_migrations(name) VALUES (%s)', (path.name,))

if __name__ == '__main__':
    migrate()
    print('Database schema is ready.')
