#!/usr/bin/env python3
"""Manifest-driven deployer for WordPress block-theme sites.

One entry point for every target (pages, template parts, global styles, media)
instead of a hand-written script per resource. Targets are declared in a
manifest JSON file; source paths are relative to the MANIFEST'S DIRECTORY.
See SKILL.md "Manifest targets" for the manifest format.

Usage:
  python3 deploy.py --manifest <path> --list          # show targets
  python3 deploy.py --manifest <path> all --dry-run   # validate sources, no writes
  python3 deploy.py --manifest <path> changed         # what differs from the site, plus media
  python3 deploy.py --manifest <path> <target> ...    # these targets
  python3 deploy.py --manifest <path> all             # every target, in order
  python3 deploy.py --manifest <path> changed --overwrite homepage  # even over its wp-admin edit

Before any write, every target to be written is checked against the site and
git history (verify_deploy.py --history): one whose live content matches no
commit (EDITED) was edited in wp-admin, and the deploy stops without writing
anything unless that target is named in --overwrite (bare --overwrite: all).
`changed` picks the targets that are BEHIND or EDITED, plus media; it reads
the site even with --dry-run, which otherwise never contacts the server.

After each write the target is read back and must match its sources
(verify_deploy.py), and a global-styles target with `markers` must still carry
them in its custom CSS (verify_global_css.py); the run stops at the first
target that fails. Structural targets are backed up and gated by
save_structural (confirm + balanced markup). Global-styles targets are
JSON-backed-up by apply_global_styles. Media targets upload a directory of
files, reusing existing attachments by filename; a failed file is reported and
the batch continues, but the run raises.
"""
import argparse
import json
import sys
from pathlib import Path

import verify_global_css
import wp_block_api as wp


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
        raise RuntimeError(f"{len(failed)} of {len(files)} media uploads failed: "
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


def _verify():
    import verify_deploy  # late: verify_deploy imports this module
    return verify_deploy


def plan(selector, manifest, base):
    """{name: status} from verify_deploy.check_target(history=True) for the
    non-media targets `selector` may write, printed with their diffs."""
    verify = _verify()
    candidates = list(manifest) if selector in (["all"], ["changed"]) else selector
    statuses = {}
    for n in candidates:
        if manifest[n]["type"] == "media":
            continue
        try:
            status, detail = verify.check_target(n, manifest[n], base, show_diff=True, history=True)
        except Exception as exc:  # a target that cannot be read is not a pass
            sys.exit(f"error: live site not readable ({n}: {type(exc).__name__}: {exc})")
        statuses[n] = status
        print(f"  {status.upper():6} {n:20} {detail}")
    return statuses


def select(selector, manifest, statuses):
    """Target names in manifest order: `all`, `changed` (BEHIND, EDITED, media) or the names given."""
    if selector == ["all"]:
        return list(manifest)
    if selector == ["changed"]:
        return [n for n, t in manifest.items()
                if t["type"] == "media" or statuses.get(n) in ("behind", "edited")]
    return [n for n in manifest if n in selector]


def refuse_edited(names, statuses, overwrite):
    """Exit before the first write if a target serves an edit from wp-admin."""
    edited = [n for n in names if statuses.get(n) == "edited"
              and "all" not in overwrite and n not in overwrite]
    if edited:
        sys.exit(
            f"error: not deployed: {', '.join(edited)} serve content that no commit has, "
            "an edit in wp-admin (diff above). Port it into data/ or decide to drop "
            f"it, then deploy with --overwrite {' '.join(edited)}."
        )


def check_written(name, t, base):
    """Exit if the site does not serve what was just written to `name`."""
    status, detail = _verify().check_target(name, t, base, show_diff=True)
    if status not in ("match", "skip"):
        sys.exit(f"error: {name}: live differs after the write: {detail}\n"
                 "Undo with rollback.py from the backup.")
    if status == "match":
        print(f"  verified: live matches ({detail})")
    if t.get("markers"):
        css = (wp.get_global_styles().get("styles") or {}).get("css") or ""
        if verify_global_css.check(css, t["markers"], t.get("icon_marker")):
            sys.exit(f"error: {name}: custom CSS lost rules on save (see above).")


def deploy_one(name, manifest, base, dry_run=False):
    t = manifest[name]
    print(f"[{name}]")
    if t["type"] == "global-styles":
        return _deploy_global_styles(name, t, base, dry_run)
    if t["type"] == "media":
        return _deploy_media(name, t, base, dry_run)
    return _deploy_structural(name, t, base, dry_run)


def _names(values):
    """Target names from arguments that may each hold several, space- or comma-separated."""
    return [n for v in values for n in v.replace(",", " ").split()]


def main(argv):
    parser = argparse.ArgumentParser(description="Manifest-driven WordPress deployer")
    parser.add_argument("--manifest", required=True, help="path to the manifest JSON")
    parser.add_argument("targets", nargs="*",
                        help="target names from --list, 'all', or 'changed'")
    parser.add_argument("--list", action="store_true", help="list targets and exit")
    parser.add_argument("--dry-run", action="store_true", help="validate sources, no writes")
    parser.add_argument("--overwrite", nargs="?", const="all", default="",
                        help="targets whose wp-admin edit may be overwritten "
                             "(space- or comma-separated; bare: all)")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text())
    base = manifest_path.parent

    if args.list:
        for k, v in manifest.items():
            print(f"  {k}: {v['type']}")
        return
    selector, overwrite = _names(args.targets), _names([args.overwrite])
    if not selector:
        parser.error("target required (names from --list, 'all' or 'changed')")
    if len(selector) > 1 and {"all", "changed"} & set(selector):
        parser.error("'all' and 'changed' stand alone")
    for n in [n for n in selector + overwrite if n not in ("all", "changed")]:
        if n not in manifest:
            sys.exit(f"error: unknown target {n!r}; have: {', '.join(manifest)}")

    statuses = {}
    if selector == ["changed"] or not args.dry_run:
        statuses = plan(selector, manifest, base)
    names = select(selector, manifest, statuses)
    if not args.dry_run:
        refuse_edited(names, statuses, overwrite)
    print(f"{'Dry run' if args.dry_run else 'Deploying'}: {' '.join(names) or 'nothing'}")
    for n in names:
        deploy_one(n, manifest, base, dry_run=args.dry_run)
        if not args.dry_run:
            check_written(n, manifest[n], base)


if __name__ == "__main__":
    main(sys.argv[1:])
