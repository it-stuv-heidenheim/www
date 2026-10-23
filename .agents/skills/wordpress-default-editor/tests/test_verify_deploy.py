import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import scripts.verify_deploy as verify
import scripts.wp_block_api as wp

BLOCKS = "<!-- wp:paragraph -->\n<p>Hallo</p>\n<!-- /wp:paragraph -->"


@pytest.fixture
def site(tmp_path):
    """A manifest with one page target plus its local source."""
    (tmp_path / "page.html").write_text(BLOCKS)
    manifest = {
        "homepage": {
            "type": "structural", "endpoint": "pages", "id": 9,
            "source": "page.html", "status": "publish",
        }
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


def _serve(monkeypatch, raw):
    monkeypatch.setattr(
        wp, "fetch_raw", lambda endpoint, pid: {"content": {"raw": raw}, "status": "publish"}
    )


def test_matching_target_passes(site, monkeypatch, capsys):
    _serve(monkeypatch, BLOCKS)
    assert verify.main(["--manifest", str(site / "manifest.json")]) == 0
    assert "OK" in capsys.readouterr().out


def test_empty_page_is_reported_not_passed(site, monkeypatch, capsys):
    """The exact failure this script exists for: target deployed, page blank."""
    _serve(monkeypatch, "")
    assert verify.main(["--manifest", str(site / "manifest.json")]) == 1
    assert "DIFF" in capsys.readouterr().out


def test_drifted_target_exits_nonzero(site, monkeypatch):
    _serve(monkeypatch, BLOCKS.replace("Hallo", "Tschüss"))
    assert verify.main(["--manifest", str(site / "manifest.json")]) == 1


def test_diff_flag_shows_the_changed_line(site, monkeypatch, capsys):
    _serve(monkeypatch, BLOCKS.replace("Hallo", "Tschüss"))
    verify.main(["--manifest", str(site / "manifest.json"), "--diff"])
    out = capsys.readouterr().out
    assert "-<p>Hallo</p>" in out and "+<p>Tschüss</p>" in out


def test_unfetchable_target_exits_2_rather_than_passing(site, monkeypatch, capsys):
    def boom(endpoint, pid):
        raise RuntimeError("404 Not Found")

    monkeypatch.setattr(wp, "fetch_raw", boom)
    assert verify.main(["--manifest", str(site / "manifest.json")]) == 2
    assert "ERROR" in capsys.readouterr().out


def test_global_styles_css_is_compared(tmp_path, monkeypatch):
    (tmp_path / "c.css").write_text(".stuv-card{color:red}")
    (tmp_path / "tokens.json").write_text("{}")
    (tmp_path / "manifest.json").write_text(json.dumps(
        {"global-styles": {"type": "global-styles", "tokens": "tokens.json", "css": "c.css"}}
    ))
    monkeypatch.setattr(
        wp, "get_global_styles", lambda *a, **k: {"styles": {"css": ".stuv-card{color:red}"}}
    )
    assert verify.main(["--manifest", str(tmp_path / "manifest.json")]) == 0

    monkeypatch.setattr(wp, "get_global_styles", lambda *a, **k: {"styles": {"css": ""}})
    assert verify.main(["--manifest", str(tmp_path / "manifest.json")]) == 1


def test_media_target_is_skipped_not_failed(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"media": {"type": "media", "source": "media"}})
    )
    assert verify.main(["--manifest", str(tmp_path / "manifest.json")]) == 0


def test_unknown_target_name_is_rejected(site):
    with pytest.raises(SystemExit):
        verify.main(["--manifest", str(site / "manifest.json"), "nope"])


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True,
    )


@pytest.fixture
def repo(site):
    """`site` as a git repo: the page said "Alt", then "Hallo" (the working tree)."""
    (site / "page.html").write_text(BLOCKS.replace("Hallo", "Alt"))
    _git(site, "init", "-q")
    _git(site, "add", ".")
    _git(site, "commit", "-q", "-m", "alt")
    (site / "page.html").write_text(BLOCKS)
    _git(site, "commit", "-q", "-am", "neu")
    return site


def test_history_calls_an_older_commit_behind(repo, monkeypatch, capsys):
    _serve(monkeypatch, BLOCKS.replace("Hallo", "Alt"))
    assert verify.main(["--manifest", str(repo / "manifest.json"), "--history"]) == 1
    out = capsys.readouterr().out
    assert "BEHIND" in out and "(alt)" in out


def test_history_calls_content_no_commit_had_edited(repo, monkeypatch, capsys):
    _serve(monkeypatch, BLOCKS.replace("Hallo", "aus wp-admin"))
    assert verify.main(["--manifest", str(repo / "manifest.json"), "--history"]) == 3
    assert "EDITED" in capsys.readouterr().out


def test_history_without_git_counts_as_edited(site, monkeypatch):
    """No history to search must stop a deploy, not wave it through."""
    _serve(monkeypatch, BLOCKS.replace("Hallo", "Alt"))
    assert verify.check_target("homepage", json.loads(
        (site / "manifest.json").read_text())["homepage"], site, history=True)[0] == "edited"


def test_global_styles_tokens_compare_as_wordpress_stores_them(tmp_path, monkeypatch):
    palette = [{"slug": "primary", "color": "#E2001A", "name": "Rot"}]
    (tmp_path / "tokens.json").write_text(json.dumps({
        "settings": {"color": {"palette": palette}},
        "styles": {"typography": {"fontFamily": "var:preset|font-family|inter"}},
    }))
    (tmp_path / "manifest.json").write_text(json.dumps(
        {"global-styles": {"type": "global-styles", "tokens": "tokens.json"}}
    ))
    stored = {
        "settings": {"color": {"palette": {"custom": palette}}, "layout": {"x": 1}},
        "styles": {"typography": {"fontFamily": "var(--wp--preset--font-family--inter)"}},
    }
    monkeypatch.setattr(wp, "get_global_styles", lambda *a, **k: stored)
    assert verify.main(["--manifest", str(tmp_path / "manifest.json")]) == 0

    stored["settings"]["color"]["palette"]["custom"] = [{**palette[0], "color": "#000"}]
    assert verify.main(["--manifest", str(tmp_path / "manifest.json")]) == 1
