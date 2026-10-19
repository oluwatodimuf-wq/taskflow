"""Exercise real HTTP APIs with isolated databases and ephemeral ports."""
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {
    'taskflow': {'title': 'Build a portfolio', 'status': 'To do', 'priority': 'High', 'due_date': '2026-12-01'},
    'pocketledger': {'description': 'Lunch', 'kind': 'Expense', 'category': 'Food', 'amount': '1500.25', 'date': '2026-10-19'},
    'stockroom': {'name': 'Notebook', 'sku': 'BOOK-01', 'category': 'Books', 'quantity': '12', 'price': '500.50', 'reorder_level': '3'},
}


class ProjectTests(unittest.TestCase):
    def request(self, path, method='GET', data=None, headers=None):
        body = json.dumps(data).encode() if data is not None else None
        request = Request(self.url + path, data=body, method=method, headers=headers or {'Content-Type': 'application/json'})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            return response.status, json.loads(raw) if 'application/json' in response.headers.get('Content-Type', '') else raw

    def test_all_projects(self):
        for slug, sample in [("taskflow", SAMPLES["taskflow"])]:
            with self.subTest(project=slug), tempfile.TemporaryDirectory() as tmp:
                spec = importlib.util.spec_from_file_location(slug, ROOT / 'server.py')
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.DB_PATH = str(Path(tmp) / 'test.sqlite3')
                module.initialize()
                server = module.ThreadingHTTPServer(('127.0.0.1', 0), module.Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                self.url = 'http://127.0.0.1:' + str(server.server_port)
                try:
                    for path in ['/', '/app.js', '/styles.css', '/api/config']:
                        self.assertEqual(self.request(path)[0], 200)
                    self.assertEqual(self.request('/api/records')[1], [])
                    status, record = self.request('/api/records', 'POST', sample)
                    self.assertEqual(status, 201)
                    record_id = record['id']
                    path = '/api/records/' + str(record_id)
                    if slug == 'pocketledger':
                        self.assertEqual(record['amount'], 150025)
                    if slug == 'stockroom':
                        self.assertEqual(record['price'], 50050)
                        self.assertEqual(self.request('/api/records', 'POST', {**sample, 'sku': 'book-01'})[0], 409)
                    changed = {**sample, next(iter(sample)): '<script>safe text</script>'}
                    self.assertEqual(self.request(path, 'PUT', changed)[0], 200)
                    module.initialize()  # Schema initialization must not reset saved data.
                    self.assertEqual(self.request('/api/records')[1][0][next(iter(sample))], '<script>safe text</script>')
                    self.assertEqual(self.request('/api/records', 'POST', {})[0], 400)
                    self.assertEqual(self.request('/api/records', 'POST', [sample])[0], 400)
                    self.assertEqual(self.request('/api/records', 'POST', {**sample, 'extra': 'bad'})[0], 400)
                    self.assertEqual(self.request('/api/records', 'POST', sample, {'Content-Type': 'text/plain'})[0], 415)
                    self.assertEqual(self.request(path, 'DELETE', headers={'Origin': 'https://example.com'})[0], 403)
                    self.assertEqual(self.request('/api/records/99999', 'PUT', sample)[0], 404)
                    self.assertEqual(self.request('/api/records/99999', 'DELETE')[0], 404)
                    for field in module.FIELDS:
                        invalid = {'integer': '-1', 'money': '1.001', 'date': '2026-02-30', 'select': 'invalid', 'text': ' '}
                        self.assertEqual(self.request('/api/records', 'POST', {**sample, field['name']: invalid[field['type']]})[0], 400)
                    self.assertEqual(self.request('/server.py')[0], 404)
                    self.assertEqual(self.request('/data.sqlite3')[0], 404)
                    self.assertEqual(self.request(path, 'DELETE')[0], 200)
                    self.assertEqual(self.request('/api/records')[1], [])
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()


if __name__ == '__main__':
    unittest.main()
