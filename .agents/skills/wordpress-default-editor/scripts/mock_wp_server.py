#!/usr/bin/env python3
"""
Lightweight mock WordPress REST API for testing the default editor skill.
Run: WP_USER=test WP_APP_PASS=pass python3 scripts/mock_wp_server.py
"""
import base64
import json
import logging
import math
import os
from pathlib import Path

from flask import Flask, jsonify, make_response, request

app = Flask(__name__)
# Template-part ids contain a literal '//' (theme//slug); don't collapse it.
app.url_map.merge_slashes = False

USER = os.environ.get("WP_USER", "test")
PASS = os.environ.get("WP_APP_PASS", "pass")
LOG_FILE = "/tmp/wp_mock_server.log"
DATA_FILE = Path(__file__).with_name("mock_data") / "pages.json"

logger = logging.getLogger("mock_wp_server")
logger.setLevel(logging.INFO)
_file_handler = logging.FileHandler(LOG_FILE)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
logger.addHandler(_file_handler)
logger.propagate = False

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

ACTIVE_THEME = "twentytwentyfive"
# Editable user global-styles record for the active theme (wp_global_styles post).
GLOBAL_STYLES = {
    1: {
        "id": 1,
        "title": {"raw": "Custom Styles", "rendered": "Custom Styles"},
        "settings": {},
        "styles": {},
    },
}


def _check_auth():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header[6:]).decode()
        return decoded == f"{USER}:{PASS}"
    except Exception:
        return False


def _fields_filter(data, fields):
    if not fields:
        return data
    keys = fields.split(",")
    return {k: data.get(k) for k in keys}


def _log_request():
    auth = request.headers.get("Authorization", "")
    body = ""
    if request.method in ("POST", "PUT", "PATCH"):
        body = request.get_data(as_text=True) or ""
    logger.info(
        "%s %s | Authorization: %s | body: %s",
        request.method,
        request.full_path,
        auth,
        body,
    )


@app.route("/wp-json/wp/v2/pages", methods=["GET"])
def list_pages():
    _log_request()
    if not _check_auth():
        return jsonify({"code": "rest_not_logged_in"}), 401
    fields = request.args.get("_fields")
    try:
        per_page = int(request.args.get("per_page", 10))
        page = int(request.args.get("page", 1))
        if per_page <= 0 or page <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"code": "rest_invalid_param"}), 400
    items = list(PAGES.values())
    total = len(items)
    total_pages = math.ceil(total / per_page)
    start = (page - 1) * per_page
    out = [_fields_filter(i, fields) for i in items[start:start + per_page]]
    resp = make_response(jsonify(out))
    resp.headers["X-WP-Total"] = str(total)
    resp.headers["X-WP-TotalPages"] = str(total_pages)
    return resp


@app.route("/wp-json/wp/v2/pages/<int:pid>", methods=["GET", "POST", "PUT", "PATCH"])
def single_page(pid):
    _log_request()
    if not _check_auth():
        return jsonify({"code": "rest_not_logged_in"}), 401
    if pid not in PAGES:
        return jsonify({"code": "rest_post_invalid_id"}), 404
    if request.method in ("POST", "PUT", "PATCH"):
        payload = request.get_json(force=True, silent=True) or {}
        if "content" in payload:
            content = payload["content"]
            if isinstance(content, dict):
                content = content.get("raw", "")
            PAGES[pid]["content"]["raw"] = content
            PAGES[pid]["content"]["rendered"] = content
        if "status" in payload:
            PAGES[pid]["status"] = payload["status"]
    fields = request.args.get("_fields")
    return jsonify(_fields_filter(PAGES[pid], fields))


@app.route(
    "/wp-json/wp/v2/template-parts/<path:tid>",
    methods=["GET", "POST", "PUT", "PATCH"],
)
def single_template_part(tid):
    _log_request()
    if not _check_auth():
        return jsonify({"code": "rest_not_logged_in"}), 401
    if tid not in TEMPLATE_PARTS:
        return jsonify({"code": "rest_post_invalid_id"}), 404
    if request.method in ("POST", "PUT", "PATCH"):
        payload = request.get_json(force=True, silent=True) or {}
        if "content" in payload:
            content = payload["content"]
            if isinstance(content, dict):
                content = content.get("raw", "")
            TEMPLATE_PARTS[tid]["content"]["raw"] = content
            TEMPLATE_PARTS[tid]["content"]["rendered"] = content
        if "status" in payload:
            TEMPLATE_PARTS[tid]["status"] = payload["status"]
    fields = request.args.get("_fields")
    return jsonify(_fields_filter(TEMPLATE_PARTS[tid], fields))


@app.route("/wp-json/wp/v2/blocks", methods=["GET", "POST"])
def blocks_collection():
    _log_request()
    if not _check_auth():
        return jsonify({"code": "rest_not_logged_in"}), 401
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
            "meta": payload.get("meta", {}),
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
    _log_request()
    if not _check_auth():
        return jsonify({"code": "rest_not_logged_in"}), 401
    if bid not in BLOCKS:
        return jsonify({"code": "rest_post_invalid_id"}), 404
    if request.method == "DELETE":
        return jsonify({"deleted": True, "previous": BLOCKS.pop(bid)})
    if request.method in ("POST", "PUT", "PATCH"):
        payload = request.get_json(force=True, silent=True) or {}
        if "content" in payload:
            content = payload["content"]
            if isinstance(content, dict):
                content = content.get("raw", "")
            BLOCKS[bid]["content"]["raw"] = content
            BLOCKS[bid]["content"]["rendered"] = content
        if "status" in payload:
            BLOCKS[bid]["status"] = payload["status"]
    fields = request.args.get("_fields")
    return jsonify(_fields_filter(BLOCKS[bid], fields))


@app.route("/wp-json/wp/v2/themes", methods=["GET"])
def list_themes():
    _log_request()
    if not _check_auth():
        return jsonify({"code": "rest_not_logged_in"}), 401
    base = request.host_url.rstrip("/")
    gid = next(iter(GLOBAL_STYLES))
    theme = {
        "stylesheet": ACTIVE_THEME,
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
    _log_request()
    if not _check_auth():
        return jsonify({"code": "rest_not_logged_in"}), 401
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
