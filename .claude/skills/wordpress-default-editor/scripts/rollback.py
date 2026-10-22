#!/usr/bin/env python3
"""
Rollback a page/post/template-part from /tmp/wp_backup/.
Restores both content AND status.
Usage: python3 rollback.py <id> [--endpoint pages|posts|template-parts|...]

<id> may be an integer (pages/posts) or a string like 'theme//slug' (template parts).
"""
import argparse
import os
import sys
import urllib.error

try:  # run as a script: scripts/ is on sys.path
    from wp_block_api import backup_dir, _backup_key, save_content
except ModuleNotFoundError:  # imported as scripts.rollback (tests)
    from scripts.wp_block_api import backup_dir, _backup_key, save_content


def rollback(page_id, endpoint="pages"):
    out_dir = backup_dir()
    key = _backup_key(endpoint, page_id)
    content_path = os.path.join(out_dir, f"{key}_original.txt")
    status_path = os.path.join(out_dir, f"{key}_status.txt")

    if not os.path.exists(content_path):
        print(f"No backup found for {endpoint}/{page_id}", file=sys.stderr)
        sys.exit(1)

    with open(content_path, encoding="utf-8") as f:
        content = f.read()

    status = "publish"
    if os.path.exists(status_path):
        with open(status_path, encoding="utf-8") as f:
            status = f.read().strip()

    try:
        save_content(endpoint, page_id, content, status)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} rolling back {endpoint}/{page_id}: {body}", file=sys.stderr)
        sys.exit(1)

    print(f"Rolled back {endpoint}/{page_id} to status '{status}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rollback from /tmp/wp_backup/")
    parser.add_argument("page_id", help="page/post id, or 'theme//slug' for template parts")
    parser.add_argument("--endpoint", default="pages", help="WP REST endpoint (default: pages)")
    args = parser.parse_args()
    rollback(args.page_id, args.endpoint)
