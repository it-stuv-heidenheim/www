#!/usr/bin/env python3
"""
Lightweight mock WordPress REST API for testing the default editor skill.
Run: WP_USER=test WP_APP_PASS=pass python3 scripts/mock_wp_server.py
"""
import base64
import json
import os
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)
# Template-part ids contain a literal '//' (theme//slug); don't collapse it.
app.url_map.merge_slashes = False

USER = os.environ.get("WP_USER", "test")
PASS = os.environ.get("WP_APP_PASS", "pass")
DATA_FILE = Path(__file__).with_name("mock_data") / "pages.json"

with DATA_FILE.open(encoding="utf-8") as f:
    PAGES = {p["id"]: p for p in json.load(f)["pages"]}

TEMPLATE_PARTS = {
    "twentytwentyfive//header": {
        "id": "twentytwentyfive//header",
        "title": {"raw": "Header", "rendered": "Header"},
        "content": {
            "raw": "<!-- wp:site-title /-->",
            "rendered": "<!-- wp:site-title /-->",
        },
        "status": "publish",
    },
}

BLOCKS = {}
_next_block_id = [100]

GLOBAL_STYLES = {1: {"id": 1, "settings": {}, "styles": {}}}


@app.before_request
def _check_auth():
    auth_header = request.headers.get("Authorization", "")
    try:
        decoded = base64.b64decode(auth_header[6:]).decode()
        ok = auth_header.startswith("Basic ") and decoded == f"{USER}:{PASS}"
    except Exception:
        ok = False
    if not ok:
        return jsonify({"code": "rest_not_logged_in"}), 401


def _fields_filter(data, fields):
    if not fields:
        return data
    keys = fields.split(",")
    return {k: data.get(k) for k in keys}


def _single(store, key):
    """GET or update (content, status) one record of `store`, as WordPress does."""
    if key not in store:
        return jsonify({"code": "rest_post_invalid_id"}), 404
    if request.method in ("POST", "PUT", "PATCH"):
        payload = request.get_json(force=True, silent=True) or {}
        if "content" in payload:
            content = payload["content"]
            if isinstance(content, dict):
                content = content.get("raw", "")
            store[key]["content"] = {"raw": content, "rendered": content}
        if "status" in payload:
            store[key]["status"] = payload["status"]
    return jsonify(_fields_filter(store[key], request.args.get("_fields")))


@app.route("/wp-json/wp/v2/pages", methods=["GET"])
def list_pages():
    fields = request.args.get("_fields")
    return jsonify([_fields_filter(p, fields) for p in PAGES.values()])


@app.route("/wp-json/wp/v2/pages/<int:pid>", methods=["GET", "POST", "PUT", "PATCH"])
def single_page(pid):
    return _single(PAGES, pid)


@app.route(
    "/wp-json/wp/v2/template-parts/<path:tid>",
    methods=["GET", "POST", "PUT", "PATCH"],
)
def single_template_part(tid):
    return _single(TEMPLATE_PARTS, tid)


@app.route("/wp-json/wp/v2/blocks", methods=["GET", "POST"])
def blocks_collection():
    if request.method == "POST":
        payload = request.get_json(force=True, silent=True) or {}
        bid = _next_block_id[0]
        _next_block_id[0] += 1
        content = payload.get("content", "")
        if isinstance(content, dict):
            content = content.get("raw", "")
        title = payload.get("title", "")
        BLOCKS[bid] = {
            "id": bid,
            "title": {"raw": title, "rendered": title},
            "slug": payload.get("slug", ""),
            "content": {"raw": content, "rendered": content},
            "status": payload.get("status", "publish"),
        }
        return jsonify(BLOCKS[bid]), 201
    slug = request.args.get("slug")
    fields = request.args.get("_fields")
    items = [b for b in BLOCKS.values() if slug is None or b["slug"] == slug]
    return jsonify([_fields_filter(i, fields) for i in items])


@app.route(
    "/wp-json/wp/v2/blocks/<int:bid>",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
def single_block(bid):
    if request.method == "DELETE" and bid in BLOCKS:
        return jsonify({"deleted": True, "previous": BLOCKS.pop(bid)})
    return _single(BLOCKS, bid)


@app.route("/wp-json/wp/v2/themes", methods=["GET"])
def list_themes():
    base = request.host_url.rstrip("/")
    gid = next(iter(GLOBAL_STYLES))
    theme = {
        "status": "active",
        "_links": {
            "wp:user-global-styles": [
                {"href": f"{base}/wp-json/wp/v2/global-styles/{gid}"}
            ]
        },
    }
    return jsonify([theme])


@app.route(
    "/wp-json/wp/v2/global-styles/<int:gid>",
    methods=["GET", "POST", "PUT", "PATCH"],
)
def single_global_styles(gid):
    if gid not in GLOBAL_STYLES:
        return jsonify({"code": "rest_post_invalid_id"}), 404
    if request.method in ("POST", "PUT", "PATCH"):
        payload = request.get_json(force=True, silent=True) or {}
        # The client deep-merges then sends the full subtree; store it verbatim.
        if "settings" in payload:
            GLOBAL_STYLES[gid]["settings"] = payload["settings"]
        if "styles" in payload:
            GLOBAL_STYLES[gid]["styles"] = payload["styles"]
    fields = request.args.get("_fields")
    return jsonify(_fields_filter(GLOBAL_STYLES[gid], fields))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("WP_MOCK_PORT", "5001")))
