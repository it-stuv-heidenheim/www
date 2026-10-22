#!/usr/bin/env python3
"""Manifest-driven deployer for WordPress block-theme sites.

One entry point for every target (pages, template parts, global styles, media)
instead of a hand-written script per resource. Targets are declared in a
manifest JSON file; source paths are relative to the MANIFEST'S DIRECTORY.
See SKILL.md "Manifest-driven site deploys" for the manifest format.

Usage:
  python3 deploy.py --manifest <path> --list          # show targets
  python3 deploy.py --manifest <path> all --dry-run   # validate sources, no writes
  python3 deploy.py --manifest <path> <target>        # deploy one target
  python3 deploy.py --manifest <path> all             # deploy every target, in order

Structural targets are backed up and gated by save_structural (confirm +
balanced markup). Global-styles targets are JSON-backed-up by apply_global_styles.
Media targets upload a directory of files, reusing existing attachments by
filename; a failed file is reported and the batch continues, but the run raises.
"""
import argparse
import json
import sys
from pathlib import Path

try:  # run as a script: scripts/ is on sys.path
    import wp_block_api as wp
except ModuleNotFoundError:  # imported as scripts.deploy (tests)
    import scripts.wp_block_api as wp


def _read_source(base, rel):
    """A source is either one .html file or a directory of *.html joined in name order."""
    path = base / rel
    if path.is_dir():
        files = sorted(path.glob("*.html"))
        if not files:
            raise FileNotFoundError(f"no *.html in {path}")
        return "\n\n".join(f.read_text() for f in files)
    return path.read_text()


def _deploy_structural(name, t, base, dry_run):
    content = _read_source(base, t["source"])
    wp.assert_balanced_blocks(content)  # fail fast, before any write
    endpoint, rid, status = t["endpoint"], t["id"], t.get("status")
    if dry_run:
        print(f"  [dry-run] {endpoint}/{rid} <- {t['source']} "
              f"({len(content)} bytes, balanced OK)")
        return None
    status = status or wp.fetch_raw(endpoint, rid)["status"]
    wp.backup(endpoint, rid)
    result = wp.save_structural(endpoint, rid, content, status, confirm=True)
    print(f"  {endpoint}/{rid} <- {t['source']} ({len(content)} bytes, status={status})")
    return result


def _deploy_media(name, t, base, dry_run):
    source_dir = base / t["source"]
    if not source_dir.is_dir():
        raise FileNotFoundError(f"media source {t['source']} is not a directory")
    files = sorted(f for f in source_dir.iterdir() if f.is_file() and not f.name.startswith("."))
    if not files:
        print(f"  no media files in {t['source']}")
        return None
    if dry_run:
        for f in files:
            print(f"  [dry-run] upload {f.name} ({f.stat().st_size} bytes)")
        return None
    results, failed = [], []
    for f in files:
        try:
            result = wp.upload_media(str(f), reuse_existing=True)
            results.append(result)
            print(f"  {f.name} -> {result['source_url']} (id {result['id']})")
        except Exception as exc:
            # One unuploadable file shouldn't abort the rest of the batch, but the
            # run must still exit non-zero rather than look like a clean deploy.
            failed.append(f"{f.name}: {exc}")
            print(f"  SKIP {f.name}: {exc}")
    if failed:
        raise RuntimeError(f"{len(failed)} of {len(files)} media uploads failed — "
                           + "; ".join(failed))
    return results


def _deploy_global_styles(name, t, base, dry_run):
    tokens = json.loads((base / t["tokens"]).read_text())
    styles = tokens.get("styles") or {}
    css_rel = t.get("css")
    if css_rel:
        styles = {**styles, "css": _read_source(base, css_rel)}
    if dry_run:
        groups = list((tokens.get("settings") or {}).keys())
        css_note = f", css {len(styles.get('css', ''))} bytes" if css_rel else ""
        print(f"  [dry-run] global-styles <- {t['tokens']}{css_note} "
              f"(settings: {', '.join(groups)})")
        return None
    result = wp.apply_global_styles(tokens.get("settings"), styles, confirm=True)
    print(f"  global-styles updated (id {result.get('id')})")
    return result


def deploy_one(name, manifest, base, dry_run=False):
    t = manifest[name]
    print(f"[{name}]")
    if t["type"] == "global-styles":
        return _deploy_global_styles(name, t, base, dry_run)
    if t["type"] == "media":
        return _deploy_media(name, t, base, dry_run)
    return _deploy_structural(name, t, base, dry_run)


def main(argv):
    parser = argparse.ArgumentParser(description="Manifest-driven WordPress deployer")
    parser.add_argument("--manifest", required=True, help="path to the manifest JSON")
    parser.add_argument("target", nargs="?", help="a target name from --list, or 'all'")
    parser.add_argument("--list", action="store_true", help="list targets and exit")
    parser.add_argument("--dry-run", action="store_true", help="validate sources, no writes")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text())
    base = manifest_path.parent

    if args.list:
        for k, v in manifest.items():
            print(f"  {k}: {v['type']}")
        return
    if not args.target:
        parser.error("target required (a name from --list, or 'all')")
    names = list(manifest) if args.target == "all" else [args.target]
    for n in names:
        if n not in manifest:
            sys.exit(f"unknown target {n!r}; have: {', '.join(manifest)}")
    for n in names:
        deploy_one(n, manifest, base, dry_run=args.dry_run)


if __name__ == "__main__":
    main(sys.argv[1:])
