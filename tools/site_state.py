#!/usr/bin/env python3
"""Snapshot the site state that lives only in WordPress, and check it for drift.

deploy.py writes block content, template parts and global styles; everything
else is set in wp-admin and stored only in the database: site settings, the
active theme and plugins, page titles, slugs and templates, The SEO
Framework's titles, descriptions and preview image, and the WPForms fields.
Library files are listed only when data/media/ lacks them: uploaded in
wp-admin, or left over after their file was removed from the repo. data/site-state.json records it, so a change shows up as a diff and a
lost database can be set up again from the file.

Nothing is written to the site, and this does not restore anything: the file
is the record to re-enter by hand. Sources are the REST API (admin
credentials, like deploy.py) and the served pages, read with a query string
so WP-Optimize's page cache is bypassed.

Left out on purpose: the admin e-mail address, because the repo is public, and
everything neither source shows, above all the WPForms notifications (who
receives a message). Keep those in a WPForms export outside this repo.

Exit codes: 0 the site matches the file, 1 it differs (diff printed),
2 the site could not be read.

Usage, from the repo root after `source .env`:
    python3 tools/site_state.py           # compare live with data/site-state.json
    python3 tools/site_state.py --write   # record the live state in the file
"""

import argparse
import difflib
import json
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser

import sitecheck as sc

STATE_PATH = sc.DATA / "site-state.json"
SKILL_SCRIPTS = sc.REPO / ".agents" / "skills" / "wordpress-default-editor" / "scripts"

# /wp/v2/settings fields worth recording. Not "email": see the docstring.
SETTINGS = (
    "title", "description", "url", "language", "timezone", "date_format", "time_format",
    "start_of_week", "show_on_front", "page_on_front", "page_for_posts", "posts_per_page",
    "default_comment_status", "default_ping_status", "site_icon", "site_logo",
)
PAGE_FIELDS = ("id", "status", "template", "parent", "menu_order", "comment_status", "ping_status", "featured_media")
SEO_META = (
    "description", "robots", "og:type", "og:title", "og:description", "og:image",
    "twitter:card", "twitter:title", "twitter:description", "twitter:image",
)
FIELD_CONTAINER_RE = re.compile(r"wpforms-(\d+)-field_(\d+)-container")


class Served(HTMLParser):
    """The SEO tags of a served page's <head> and the WPForms forms in its body."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.seo = {}
        self.forms = {}
        self._field = None
        self._in = None  # "title", "label" (or legend), "option" or "submit" while collecting text
        self._text = []
        self._star = False  # inside the "*" of a required label, which is not label text
        self._form = None
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if tag == "title":
            self._start("title")
        elif tag == "meta" and (a.get("name") or a.get("property")) in SEO_META:
            self.seo[a.get("name") or a.get("property")] = a.get("content")
        elif tag == "link" and a.get("rel") == "canonical":
            self.seo["canonical"] = a.get("href")
        elif tag == "form" and (a.get("id") or "").startswith("wpforms-form-"):
            self._form = self.forms.setdefault(a["id"].removeprefix("wpforms-form-"), {"fields": []})
        elif tag == "div" and self._form is not None and FIELD_CONTAINER_RE.fullmatch(a.get("id") or ""):
            if "data-field-type" in a:
                # WPForms' honeypot: a hidden decoy for spam bots, with a field
                # id and a label drawn at random on every page view. Real
                # fields carry no data-field-type.
                self._field = None
                return
            kind = next((c.removeprefix("wpforms-field-") for c in classes
                         if c.startswith("wpforms-field-") and c != "wpforms-field-required"), None)
            self._field = {"id": int(FIELD_CONTAINER_RE.fullmatch(a["id"]).group(2)), "type": kind,
                           "label": "", "required": False}
            self._form["fields"].append(self._field)
        elif self._field is not None and tag in ("label", "legend") and "wpforms-field-label" in classes:
            # A first/last name pair is a <fieldset> labelled by a <legend>.
            self._start("label")
        elif self._field is not None and tag == "span" and "wpforms-required-label" in classes:
            self._field["required"] = True
            self._star = True
        elif self._field is not None and tag == "option":
            self._start("option")
        elif self._form is not None and tag == "button" and a.get("type") == "submit":
            self._start("submit")

    def handle_endtag(self, tag):
        if tag == "span":
            self._star = False
        text = " ".join("".join(self._text).split())
        if tag == "title" and self._in == "title":
            self.seo["title"] = text
        elif tag in ("label", "legend") and self._in == "label":
            self._field["label"] = text
        elif tag == "option" and self._in == "option":
            self._field.setdefault("options", []).append(text)
        elif tag == "button" and self._in == "submit":
            self._form["submit"] = text
        elif tag == "form":
            self._form = self._field = None
        if tag in ("title", "label", "legend", "option", "button"):
            self._in, self._text = None, []

    def handle_data(self, data):
        if self._in and not self._star:
            self._text.append(data)

    def _start(self, what):
        self._in, self._text = what, []


def fetch_state():
    sys.path.insert(0, str(SKILL_SCRIPTS))
    import wp_block_api as wp

    # The client has no public calls for these routes; _request and _opener
    # carry the auth, retries and the IPv4 fallback the host needs.
    settings = wp._request("GET", "settings")
    theme = wp._request("GET", "themes?status=active&_fields=stylesheet")
    plugins = wp._request("GET", "plugins?_fields=plugin,status")
    pages = wp._request(
        "GET",
        "pages?per_page=100&status=publish,future,draft,pending,private&context=edit"
        "&_fields=slug,title," + ",".join(PAGE_FIELDS),
    )
    media = wp._request("GET", "media?per_page=100&_fields=source_url")
    repo_media = {p.name for p in (sc.DATA / "media").iterdir() if not p.name.startswith(".")}

    seo, forms = {}, {}
    stamp = int(time.time())
    for url in sorted(sc.pages()):
        req = urllib.request.Request(f"{wp._site()}{url}?stuv-state={stamp}", headers={"User-Agent": "stuv-check/1.0"})
        with wp._opener.open(req, timeout=30) as response:
            served = Served(response.read().decode("utf-8"))
        seo[url] = served.seo
        for form_id, form in served.forms.items():
            forms[form_id] = {"page": url, **form}

    return {
        "settings": {k: settings.get(k) for k in SETTINGS},
        "theme": ", ".join(t["stylesheet"] for t in theme),
        "plugins": {p["plugin"]: p["status"] for p in plugins},
        "pages": {
            p["slug"]: {"title": p["title"]["raw"], **{k: p[k] for k in PAGE_FIELDS}}
            for p in pages
        },
        # Files from data/media/ are the repo's own and come and go with a
        # deploy; only the rest is state the repo would not know about.
        "media_not_in_repo": sorted(
            name for name in (m["source_url"].rsplit("/", 1)[-1] for m in media) if name not in repo_media
        ),
        "seo": seo,
        "forms": forms,
    }


def dump(state):
    return json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="record the live state in data/site-state.json")
    args = parser.parse_args(argv)
    try:
        live = dump(fetch_state())
    except Exception as exc:  # noqa: BLE001 - any failure means "could not check"
        print(f"could not read the site: {exc}", file=sys.stderr)
        return 2
    if args.write:
        STATE_PATH.write_text(live)
        print(f"wrote {STATE_PATH.relative_to(sc.REPO)}")
        return 0
    recorded = dump(json.loads(STATE_PATH.read_text())) if STATE_PATH.exists() else ""
    if live == recorded:
        print("site state matches data/site-state.json")
        return 0
    sys.stdout.writelines(difflib.unified_diff(
        recorded.splitlines(keepends=True), live.splitlines(keepends=True),
        "data/site-state.json", "live site",
    ))
    print("\nChanged in wp-admin. Intended: python3 tools/site_state.py --write, then commit. "
          "Not intended: set it back in wp-admin.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
