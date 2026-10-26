#!/usr/bin/env python3
"""Fetch every external link of the deployed pages and report the dead ones.

BROKEN (exit 1): 404/410, DNS, refused connection or bad certificate, twice. WARN: 403, 429,
5xx, timeouts. MOVED: ends up on another domain. Skipped: Instagram, WhatsApp, the calendar
subscribe link and Google Maps queries.

    python3 tools/check_links.py
"""

import concurrent.futures
import http.client
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import sitecheck as sc

UNCHECKABLE = (
    "instagram.com/",
    "wa.me/",
    "chat.whatsapp.com/",
    "google.com/maps/",
    "calendar.google.com/calendar/render",
)
# Short links whose redirect to another domain is their job, not a move.
REDIRECTORS = ("forms.gle",)
BROKEN_STATUS = {404, 410}
USER_AGENT = "Mozilla/5.0 (compatible; stuv-linkcheck/1.0; +https://stuv-heidenheim.de)"
TIMEOUT = 20


def external_links():
    """{url: sorted page urls it appears on} across every page, header and footer included."""
    chrome = "".join(sc.template_parts().values())
    found = {}
    for page, markup in sc.pages().items():
        for a in sc.Doc(markup + chrome).links:
            href = a.attrs["href"].strip()
            if href.startswith(("http://", "https://")):
                found.setdefault(href, set()).add(page)
    return {url: sorted(pages) for url, pages in found.items()}


def checkable(url):
    rest = urllib.parse.urlsplit(url)
    host_path = rest.netloc.lower().removeprefix("www.") + rest.path
    return not host_path.startswith(UNCHECKABLE)


def domain(url):
    """The last two labels of the host: www. and other subdomains do not count as a move."""
    return ".".join(urllib.parse.urlsplit(url).netloc.lower().split(".")[-2:])


def fetch(url):
    """("ok" | "broken" | "warn", detail) for one attempt."""
    # Percent-encode what a browser would (a space, an umlaut); urlopen refuses it raw.
    quoted = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
    req = urllib.request.Request(quoted, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        # GET, not HEAD: enough servers answer HEAD with 405 or 404 that
        # HEAD would report links that work in a browser.
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            response.read(1024)
            final = response.geturl()
            moved = domain(final) != domain(url) and urllib.parse.urlsplit(url).netloc not in REDIRECTORS
            return "ok", f"redirects to {final}" if moved else ""
    except urllib.error.HTTPError as exc:
        return ("broken" if exc.code in BROKEN_STATUS else "warn"), f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, (socket.gaierror, ConnectionRefusedError, ssl.SSLCertVerificationError)):
            return "broken", f"{type(reason).__name__}: {reason}"
        return "warn", f"{type(reason).__name__}: {reason}"
    except (TimeoutError, OSError, http.client.HTTPException) as exc:
        return "warn", f"{type(exc).__name__}: {exc}"


def check(url):
    verdict, detail = fetch(url)
    if verdict != "ok":
        time.sleep(5)
        verdict, detail = fetch(url)
    return verdict, detail


def main():
    links = external_links()
    urls = sorted(u for u in links if checkable(u))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(urls, pool.map(check, urls)))
    broken = 0
    for url, (verdict, detail) in results.items():
        if verdict == "ok" and not detail:
            continue
        label = {"ok": "MOVED", "broken": "BROKEN", "warn": "WARN"}[verdict]
        print(f"{label:6} {url}\n       {detail}; on {', '.join(links[url])}")
        broken += verdict == "broken"
    print(f"{len(urls)} links checked, {len(links) - len(urls)} skipped, {broken} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
