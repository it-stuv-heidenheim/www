#!/usr/bin/env python3
"""
Restore a page/post/template part (content and status), a replaced image, or the global
styles from the backup the last write took.
Usage: python3 rollback.py <id> [--endpoint pages|posts|template-parts|...]   # id: 12 or 'theme//slug'
       python3 rollback.py --media <filename>
       python3 rollback.py --global-styles
"""
import argparse
import json
import os
import sys
import urllib.error

import wp_block_api as wp


def rollback(page_id, endpoint="pages"):
    out_dir = wp.backup_dir()
    key = wp._backup_key(endpoint, page_id)
    content_path = os.path.join(out_dir, f"{key}_original.txt")
    status_path = os.path.join(out_dir, f"{key}_status.txt")

    if not os.path.exists(content_path):
        sys.exit(f"No backup found for {endpoint}/{page_id}")

    with open(content_path, encoding="utf-8") as f:
        content = f.read()

    status = "publish"
    if os.path.exists(status_path):
        with open(status_path, encoding="utf-8") as f:
            status = f.read().strip()

    wp.save_content(endpoint, page_id, content, status)
    print(f"Rolled back {endpoint}/{page_id} to status '{status}'.")


def rollback_media(filename):
    path, meta_path = wp.media_backup_paths(filename)
    if not os.path.exists(path):
        sys.exit(f"No media backup found for {filename}")
    alt_text = None
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            alt_text = json.load(f).get("alt_text") or None
    # backup=False: a backup now would overwrite the one being restored.
    new = wp.replace_media(path, filename=filename, alt_text=alt_text, backup=False)
    print(f"Restored {filename} at {new['source_url']} (id {new['id']}).")


def rollback_global_styles():
    """POST back the record apply_global_styles() saved, in the shape WordPress reads it back."""
    gid = wp.discover_global_styles_id()
    path = wp.global_styles_backup_path(gid)
    if not os.path.exists(path):
        sys.exit(f"No global-styles backup found at {path}")
    with open(path, encoding="utf-8") as f:
        record = json.load(f)
    fields = {k: record.get(k) or {} for k in ("settings", "styles")}
    wp._request("POST", f"global-styles/{gid}", data=json.dumps(fields).encode())
    print(f"Rolled back global-styles/{gid}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rollback from /tmp/wp_backup/")
    parser.add_argument("page_id", nargs="?", help="page/post id, or 'theme//slug' for template parts")
    parser.add_argument("--endpoint", default="pages", help="WP REST endpoint (default: pages)")
    parser.add_argument("--media", metavar="FILENAME", help="restore an image replaced by replace_media()")
    parser.add_argument("--global-styles", action="store_true",
                        help="restore the global styles the last deploy overwrote")
    args = parser.parse_args()
    if [args.page_id is not None, args.media is not None, args.global_styles].count(True) != 1:
        parser.error("give one of: an id, --media FILENAME, --global-styles")
    try:
        if args.media:
            rollback_media(args.media)
        elif args.global_styles:
            rollback_global_styles()
        else:
            rollback(args.page_id, args.endpoint)
    except urllib.error.HTTPError as exc:
        sys.exit(str(exc))
