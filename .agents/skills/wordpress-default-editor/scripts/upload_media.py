#!/usr/bin/env python3
"""
Upload files to the media library and print their source_url. An existing filename is reused;
--replace puts the file under the existing URL (undo: rollback.py --media).

Usage:
  python3 -m scripts.upload_media <file> [<file> ...] [--alt "text"] [--replace]
"""
import argparse
import sys
import urllib.error

try:  # run as a script: scripts/ is on sys.path
    import wp_block_api as wp
except ModuleNotFoundError:  # run as python3 -m scripts.upload_media
    from scripts import wp_block_api as wp


def main(argv):
    parser = argparse.ArgumentParser(description="Upload files to the WP media library")
    parser.add_argument("files", nargs="+", help="local file path(s) to upload")
    parser.add_argument("--alt", default=None, help="alt text applied to each upload")
    parser.add_argument("--replace", action="store_true", help="replace a same-named attachment at its URL")
    args = parser.parse_args(argv)

    for path in args.files:
        try:
            if args.replace:
                result = wp.replace_media(path, alt_text=args.alt)
            else:
                result = wp.upload_media(path, alt_text=args.alt)
        except urllib.error.HTTPError as exc:
            sys.exit(f"{path}: {exc}")
        print(f"{path} -> {result['source_url']} (id {result['id']})")


if __name__ == "__main__":
    main(sys.argv[1:])
