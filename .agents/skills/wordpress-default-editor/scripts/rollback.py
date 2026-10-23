#!/usr/bin/env python3
"""
Rollback a page/post/template-part, or a replaced image, from /tmp/wp_backup/.
Restores both content AND status; an image goes back under its old URL.
Usage: python3 rollback.py <id> [--endpoint pages|posts|template-parts|...]
       python3 rollback.py --media <filename>

<id> may be an integer (pages/posts) or a string like 'theme//slug' (template parts).
--media restores the file replace_media() backed up before it deleted the
attachment. The file it removes again is not backed up: it is the one just
uploaded, so the caller has it.
"""
import argparse
import json
import os
import sys
import urllib.error

try:  # run as a script: scripts/ is on sys.path
    from wp_block_api import backup_dir, _backup_key, media_backup_paths, replace_media, save_content
except ModuleNotFoundError:  # imported as scripts.rollback (tests)
    from scripts.wp_block_api import backup_dir, _backup_key, media_backup_paths, replace_media, save_content


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


def rollback_media(filename):
    path, meta_path = media_backup_paths(filename)
    if not os.path.exists(path):
        print(f"No media backup found for {filename}", file=sys.stderr)
        sys.exit(1)
    alt_text = None
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            alt_text = json.load(f).get("alt_text") or None
    try:
        # backup=False: a backup now would overwrite the one being restored.
        new = replace_media(path, filename=filename, alt_text=alt_text, backup=False)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} restoring {filename}: {body}", file=sys.stderr)
        sys.exit(1)
    print(f"Restored {filename} at {new['source_url']} (id {new['id']}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rollback from /tmp/wp_backup/")
    parser.add_argument("page_id", nargs="?", help="page/post id, or 'theme//slug' for template parts")
    parser.add_argument("--endpoint", default="pages", help="WP REST endpoint (default: pages)")
    parser.add_argument("--media", metavar="FILENAME", help="restore an image replaced by replace_media()")
    args = parser.parse_args()
    if (args.page_id is None) == (args.media is None):
        parser.error("give either an id or --media FILENAME")
    if args.media:
        rollback_media(args.media)
    else:
        rollback(args.page_id, args.endpoint)
