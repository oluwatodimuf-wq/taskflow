"""Local portfolio demo API and static server. Python 3.10+, no dependencies."""
import json
import os
import re
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'project.json').read_text())
FIELDS = CONFIG['fields']
DB_PATH = os.environ.get('DATABASE_PATH', str(ROOT / 'data.sqlite3'))


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    columns = ', '.join('"' + f['name'] + '" ' + ('INTEGER' if f['type'] in ('integer', 'money') else 'TEXT') + ' NOT NULL' for f in FIELDS)
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY AUTOINCREMENT, ' + columns + ', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        if CONFIG['slug'] == 'stockroom':
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS records_sku ON records(sku COLLATE NOCASE)')


def validate(payload):
    if not isinstance(payload, dict):
        raise ValueError('Expected a JSON object.')
    if set(payload) != {f['name'] for f in FIELDS}:
        raise ValueError('Supply exactly the required fields.')
    clean = {}
    for f in FIELDS:
        value = payload[f['name']]
        kind = f['type']
        if kind == 'integer':
            if isinstance(value, bool) or not re.fullmatch(r'[0-9]{1,9}', str(value)):
                raise ValueError(f['label'] + ' must be a nonnegative whole number (up to 999999999).')
            value = int(value)
        elif kind == 'money':
            if isinstance(value, bool) or not re.fullmatch(r'[0-9]{1,9}(?:\.[0-9]{1,2})?', str(value)):
                raise ValueError(f['label'] + ' must be a positive amount with up to two decimal places.')
            value = int(Decimal(str(value)) * 100)
            if value <= 0:
                raise ValueError(f['label'] + ' must be greater than zero.')
        else:
            if not isinstance(value, str):
                raise ValueError(f['label'] + ' must be text.')
            value = value.strip()
            if not value or len(value) > f.get('max', 120):
                raise ValueError(f['label'] + ' is required and must fit the length limit.')
            if kind == 'select' and value not in f['options']:
                raise ValueError('Invalid ' + f['label'].lower() + '.')
            if kind == 'date':
                try:
                    date.fromisoformat(value)
                except ValueError:
                    raise ValueError(f['label'] + ' must be a valid YYYY-MM-DD date.')
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    raise ValueError('Use YYYY-MM-DD for dates.')
        clean[f['name']] = value
    return clean


class Handler(BaseHTTPRequestHandler):
    def json_response(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/config':
            return self.json_response(200, CONFIG)
        if path == '/api/records':
            with connect() as db:
                rows = [dict(r) for r in db.execute('SELECT * FROM records ORDER BY id DESC')]
            return self.json_response(200, rows)
        allowed = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/styles.css': ('styles.css', 'text/css')}
        if path not in allowed:
            return self.json_response(404, {'error': 'Not found.'})
        name, mime = allowed[path]
        data = (ROOT / 'public' / name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def mutate(self, method):
        path = urlsplit(self.path).path
        match = re.fullmatch(r'/api/records/([1-9][0-9]*)', path)
        if (method == 'POST' and path != '/api/records') or (method != 'POST' and not match):
            return self.json_response(404, {'error': 'Not found.'})
        # JSON-only writes reject cross-origin HTML form submissions.
        if method != 'DELETE' and self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            return self.json_response(415, {'error': 'Use application/json.'})
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.json_response(403, {'error': 'Cross-origin writes are not allowed.'})
        try:
            record_id = int(match[1]) if match else None
            clean = None
            if method != 'DELETE':
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    return self.json_response(413, {'error': 'Request body must be 1 to 16384 bytes.'})
                clean = validate(json.loads(self.rfile.read(size)))
            with connect() as db:
                if method != 'POST' and not db.execute('SELECT id FROM records WHERE id=?', (record_id,)).fetchone():
                    return self.json_response(404, {'error': 'Record not found.'})
                if method == 'DELETE':
                    db.execute('DELETE FROM records WHERE id=?', (record_id,))
                    result = {'deleted': record_id}
                else:
                    columns = list(clean)
                    if method == 'POST':
                        sql = 'INSERT INTO records (' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')'
                        record_id = db.execute(sql, tuple(clean.values())).lastrowid
                    else:
                        sql = 'UPDATE records SET ' + ','.join(c + '=?' for c in columns) + ' WHERE id=?'
                        db.execute(sql, (*clean.values(), record_id))
                    result = dict(db.execute('SELECT * FROM records WHERE id=?', (record_id,)).fetchone())
            return self.json_response(201 if method == 'POST' else 200, result)
        except sqlite3.IntegrityError:
            return self.json_response(409, {'error': 'That SKU already exists.'})
        except (ValueError, InvalidOperation, UnicodeDecodeError) as error:
            return self.json_response(400, {'error': str(error) or 'Invalid request.'})
        except sqlite3.Error:
            return self.json_response(503, {'error': 'Database unavailable. Try again.'})

    def do_POST(self):
        self.mutate('POST')

    def do_PUT(self):
        self.mutate('PUT')

    def do_DELETE(self):
        self.mutate('DELETE')


if __name__ == '__main__':
    initialize()
    port = int(os.environ.get('PORT', CONFIG['port']))
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f"{CONFIG['title']} running at http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
