#!/usr/bin/env python3
"""
Upload local files to the WP media library and print their source_url.

Usage:
  python3 -m scripts.upload_media <file> [<file> ...] [--alt "text"]

Re-running with the same filename is a no-op (returns the existing attachment)
unless --force is passed. With multiple files, --alt applies to all of them;
for per-file alt text, run the script once per file.
"""
import argparse
import sys
import urllib.error

try:  # run as a script: scripts/ is on sys.path
    from wp_block_api import upload_media
except ModuleNotFoundError:  # imported as scripts.upload_media (tests, -m)
    from scripts.wp_block_api import upload_media


def main(argv):
    parser = argparse.ArgumentParser(description="Upload files to the WP media library")
    parser.add_argument("files", nargs="+", help="local file path(s) to upload")
    parser.add_argument("--alt", default=None, help="alt text applied to each upload")
    parser.add_argument("--force", action="store_true", help="re-upload even if a same-named attachment exists")
    args = parser.parse_args(argv)

    for path in args.files:
        try:
            result = upload_media(path, alt_text=args.alt, reuse_existing=not args.force)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            print(f"HTTP {exc.code} uploading {path}: {body}", file=sys.stderr)
            sys.exit(1)
        print(f"{path} -> {result['source_url']} (id {result['id']})")


if __name__ == "__main__":
    main(sys.argv[1:])
