import base64
import copy
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

# Overwrite, never setdefault: a sourced .env would point the writing tests at the real site.
os.environ["WP_USER"] = "test"
os.environ["WP_APP_PASS"] = "pass"
os.environ["WP_SITE"] = "http://127.0.0.1:5001"
for var in ("WP_REST_ROOT", "WP_ADDRESS_FAMILY", "WP_CONNECT_TIMEOUT"):
    os.environ.pop(var, None)

SEED = {
    "pages/1": {"id": 1, "status": "publish", "content": {"raw": (
        "<!-- wp:heading -->\n<h1>Welcome to our site</h1>\n<!-- /wp:heading -->\n\n"
        "<!-- wp:paragraph -->\n<p>This is placeholder text that needs to be replaced.</p>\n"
        "<!-- /wp:paragraph -->")}},
    "pages/2": {"id": 2, "status": "draft", "content": {"raw": (
        "<!-- wp:paragraph -->\n<p>Draft placeholder.</p>\n<!-- /wp:paragraph -->")}},
    "template-parts/twentytwentyfive//header": {
        "id": "twentytwentyfive//header", "status": "publish",
        "content": {"raw": "<!-- wp:site-title /-->"}},
    "global-styles/1": {"id": 1, "settings": {}, "styles": {}},
}


class MockSite:
    """The records of one test's site, keyed by route. `fail` queues (method, status) replies
    for the next requests with that method; `requests` logs (method, path)."""

    def __init__(self):
        self.records, self.requests, self.fail, self.next_id = copy.deepcopy(SEED), [], [], 100

    def create(self, route, body, headers, base):
        """A new record; an upload whose filename is taken gets -1, as in WordPress."""
        self.next_id += 1
        if route == "media":
            name = re.search(r'filename="([^"]+)"', headers["Content-Disposition"])[1]
            if any(r.get("source_url", "").endswith("/" + name) for r in self.records.values()):
                stem, dot, ext = name.rpartition(".")
                name = f"{stem}-1{dot}{ext}"
            record = {"source_url": f"{base}/wp-content/uploads/{name}", "alt_text": "",
                      "bytes": body.decode("latin-1")}
        else:
            record = json.loads(body)
            record["content"] = {"raw": record.get("content", "")}
        self.records[f"{route}/{self.next_id}"] = record = {"id": self.next_id, **record}
        return record


class MockWordPress(BaseHTTPRequestHandler):
    """The wp/v2 routes the scripts use, answered from the server's MockSite."""

    def log_message(self, *args):
        pass

    def _reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, code, wp_code, message):
        self._reply(code, {"code": wp_code, "message": message})

    def _handle(self):
        site, url = self.server.site, urlsplit(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        site.requests.append((self.command, url.path))
        if site.fail and site.fail[0][0] == self.command:
            return self._error(site.fail.pop(0)[1], "mock_failure", "Injected failure.")
        if self.headers.get("Authorization") != "Basic " + base64.b64encode(b"test:pass").decode():
            return self._error(401, "rest_not_logged_in", "You are not currently logged in.")
        route, base = url.path.removeprefix("/wp-json/wp/v2/"), f"http://{self.headers['Host']}"
        if route == "themes":
            link = {"href": f"{base}/wp-json/wp/v2/global-styles/1"}
            return self._reply(200, [{"_links": {"wp:user-global-styles": [link]}}])
        if "/" not in route:  # a collection
            if self.command == "POST":
                return self._reply(201, site.create(route, body, self.headers, base))
            items = [r for k, r in site.records.items() if k.startswith(route + "/")]
            if "slug" in query:
                items = [r for r in items if r.get("slug") == query["slug"]]
            return self._reply(200, items)
        record = site.records.get(route)
        if record is None:
            return self._error(404, "rest_post_invalid_id", "Invalid post ID.")
        if self.command == "DELETE":
            return self._reply(200, {"deleted": True, "previous": site.records.pop(route)})
        if self.command == "POST":
            for key, value in json.loads(body).items():
                record[key] = {"raw": value} if key == "content" else value
        if "_fields" in query:
            record = {k: record.get(k) for k in query["_fields"].split(",")}
        self._reply(200, record)

    do_GET = do_POST = do_DELETE = _handle


@pytest.fixture(scope="session")
def _server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockWordPress)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()


@pytest.fixture
def mock_server(_server, monkeypatch):
    """A fresh MockSite per test, with WP_SITE pointing at it."""
    _server.site = MockSite()
    monkeypatch.setenv("WP_SITE", f"http://127.0.0.1:{_server.server_port}")
    return _server.site
