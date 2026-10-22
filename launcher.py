"""One local server, no reload process and no build tools."""
import socket
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
import uvicorn
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent

def open_when_ready():
    for _ in range(60):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1) as response:
                if response.status == 200:
                    webbrowser.open('http://127.0.0.1:8000')
                    return
        except Exception:
            time.sleep(0.5)

if __name__ == '__main__':
    if not (ROOT/'.env').exists():
        raise SystemExit('Copy .env.example to .env and configure the database first. See README.md.')
    load_dotenv(ROOT/'.env')
    try:
        with socket.socket() as s:
            s.bind(('127.0.0.1',8000))
    except OSError:
        raise SystemExit('Port 8000 is already in use. Close the other Shivam Tiles window/server or free this port.')
    threading.Thread(target=open_when_ready, daemon=True).start()
    print('Shivam Tiles: http://127.0.0.1:8000 — press Ctrl+C in this window to stop.')
    uvicorn.run('app.main:app', host='127.0.0.1', port=8000, workers=1, log_level='info')
