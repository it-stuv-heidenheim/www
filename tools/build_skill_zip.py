#!/usr/bin/env python3
"""Build the downloadable ZIP of the wordpress-default-editor skill.

The StuV site hosts the tooling as a single file so a visitor can download it
instead of cloning the separate skills repository. This script snapshots the *committed* state
of the skill from the local checkout with `git archive`:

    python3 tools/build_skill_zip.py            # -> data/media/wordpress-default-editor.zip

`git archive` ships committed files only, so gitignored installed deps
(`.venv/`, `blockcheck/node_modules/`, `__pycache__/`, `.pytest_cache/`,
`blockcheck/package-lock.json`) are excluded for free — no manual exclude list
to maintain — and uncommitted local WIP in the skill never ships. The output is
deterministic. `--prefix=wordpress-default-editor/` makes the ZIP extract to
`wordpress-default-editor/…`, so it drops cleanly into `~/.claude/skills/`.

The built ZIP is committed to this repo, matching the generated map images in
data/media/. The ZIP rides the `media` manifest target; because the attachment
URL carries the upload month, a ZIP change and the docs change that links to it
deploy together (see the runbook in the design spec / docs/content-editing.md).

If the checkout is not a git repo or the skill subtree is absent, the script
errors non-zero rather than writing a partial or empty ZIP.
"""

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The skills repo root; the skill is the subtree HEAD:wordpress-default-editor.
SKILLS_ROOT = Path("~/.claude/skills")
SUBTREE = "wordpress-default-editor"
OUTPUT = REPO / "data" / "media" / "wordpress-default-editor.zip"


def _git(root, *args, check=False):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _require_git_subtree(skills_root, subtree):
    """Fail loud and early if the checkout can't produce the archive."""
    if not skills_root.exists():
        sys.exit(f"error: skills checkout not found: {skills_root}")
    inside = _git(skills_root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        sys.exit(f"error: not a git repository: {skills_root}")
    # HEAD:<subtree> resolves only when the subtree is a committed tree.
    tree = _git(skills_root, "rev-parse", "--verify", "--quiet", f"HEAD:{subtree}")
    if tree.returncode != 0:
        sys.exit(f"error: subtree '{subtree}' not found at HEAD in {skills_root}")


def build_zip(skills_root, subtree, output):
    """Archive the committed state of `subtree` into `output` as a ZIP.

    Returns the output Path. Raises SystemExit (via _require_git_subtree) or
    CalledProcessError if the checkout or the archive command fails.
    """
    skills_root = Path(skills_root).expanduser()
    output = Path(output)
    _require_git_subtree(skills_root, subtree)
    output.parent.mkdir(parents=True, exist_ok=True)
    _git(
        skills_root,
        "archive",
        "--format=zip",
        f"--prefix={subtree}/",
        "-o",
        str(output),
        f"HEAD:{subtree}",
        check=True,
    )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--skills-root",
        default=str(SKILLS_ROOT),
        help=f"skills repo checkout (default: {SKILLS_ROOT})",
    )
    parser.add_argument(
        "--subtree",
        default=SUBTREE,
        help=f"skill subtree to archive (default: {SUBTREE})",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(OUTPUT),
        help=f"output ZIP path (default: {OUTPUT.relative_to(REPO)})",
    )
    args = parser.parse_args()

    output = build_zip(args.skills_root, args.subtree, args.output)

    with zipfile.ZipFile(output) as zf:
        names = zf.namelist()
    print(f"Wrote {output} ({output.stat().st_size} bytes, {len(names)} entries)")
    if f"{args.subtree}/SKILL.md" not in names:
        sys.exit(f"error: archive is missing {args.subtree}/SKILL.md — refusing it")
    print("Now deploy the `media` target, then update the docs download link.")


if __name__ == "__main__":
    main()
