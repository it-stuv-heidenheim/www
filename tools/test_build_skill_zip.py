"""Unit tests for tools/build_skill_zip.py. Stdlib only — no network.

Builds against a throwaway git repo fixture rather than the real
~/.claude/skills checkout, so the test is hermetic and does not depend on a
skill being installed.

Run from the repo root:
    python3 -m unittest discover -s tools -p "test_*.py" -v
"""

import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import build_skill_zip


def _git(root, *args):
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _make_skill_repo(root):
    """A minimal skills repo: one skill subtree plus gitignored installed deps.

    Mirrors the real layout closely enough to prove the two claims the design
    relies on — SKILL.md ships, gitignored deps do not.
    """
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.test")
    _git(root, "config", "user.name", "Test")

    skill = root / "wordpress-default-editor"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# skill\n")
    (skill / "scripts" / "deploy.py").write_text("print('deploy')\n")

    # A second skill must NOT end up in the single-skill archive.
    other = root / "some-other-skill"
    other.mkdir()
    (other / "SKILL.md").write_text("# other\n")

    # Gitignored installed deps: created but never committed, so git archive
    # (committed files only) drops them for free.
    (root / ".gitignore").write_text(
        ".venv/\nnode_modules/\n__pycache__/\n.pytest_cache/\n"
    )
    for rel in (
        "wordpress-default-editor/.venv/pyvenv.cfg",
        "wordpress-default-editor/scripts/blockcheck/node_modules/pkg/index.js",
        "wordpress-default-editor/scripts/__pycache__/deploy.cpython-311.pyc",
        "wordpress-default-editor/.pytest_cache/CACHEDIR.TAG",
    ):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("junk\n")

    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")


class TestBuildZip(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = self.root / "skills"
        self.repo.mkdir()
        _make_skill_repo(self.repo)
        self.out = self.root / "out" / "wordpress-default-editor.zip"

    def tearDown(self):
        self._tmp.cleanup()

    def _names(self):
        build_skill_zip.build_zip(self.repo, "wordpress-default-editor", self.out)
        with zipfile.ZipFile(self.out) as zf:
            return zf.namelist()

    def test_it_contains_the_skill_manifest_under_the_prefix(self):
        self.assertIn("wordpress-default-editor/SKILL.md", self._names())

    def test_it_creates_the_output_parent_directory(self):
        self.assertFalse(self.out.parent.exists())
        self._names()
        self.assertTrue(self.out.exists())

    def test_it_excludes_installed_deps(self):
        for name in self._names():
            self.assertNotIn("node_modules/", name)
            self.assertNotIn(".venv/", name)
            self.assertNotIn("__pycache__/", name)
            self.assertNotIn(".pytest_cache/", name)

    def test_it_ships_only_the_named_skill(self):
        for name in self._names():
            self.assertTrue(
                name.startswith("wordpress-default-editor/"), name
            )
        self.assertFalse(any("some-other-skill" in n for n in self._names()))


class TestGuards(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_checkout_exits(self):
        with self.assertRaises(SystemExit):
            build_skill_zip.build_zip(
                self.root / "nope", "wordpress-default-editor", self.root / "o.zip"
            )

    def test_non_git_directory_exits(self):
        plain = self.root / "plain"
        plain.mkdir()
        with self.assertRaises(SystemExit):
            build_skill_zip.build_zip(
                plain, "wordpress-default-editor", self.root / "o.zip"
            )

    def test_absent_subtree_exits(self):
        repo = self.root / "skills"
        repo.mkdir()
        _make_skill_repo(repo)
        with self.assertRaises(SystemExit):
            build_skill_zip.build_zip(repo, "no-such-skill", self.root / "o.zip")


if __name__ == "__main__":
    unittest.main()
