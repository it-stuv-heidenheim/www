
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import scripts.deploy as deploy
import scripts.wp_block_api as wp

BALANCED = "<!-- wp:paragraph -->\n<p>Hallo</p>\n<!-- /wp:paragraph -->"


def test_global_styles_css_injection(tmp_path, monkeypatch):
    captured = {}

    def fake_apply(settings, styles, *, confirm):
        captured["settings"] = settings
        captured["styles"] = styles
        captured["confirm"] = confirm
        return {"id": 7}

    monkeypatch.setattr(wp, "apply_global_styles", fake_apply)
    (tmp_path / "tokens.json").write_text(json.dumps(
        {"settings": {"layout": {}},
         "styles": {"typography": {"fontFamily": "x"}}}))
    (tmp_path / "c.css").write_text(".stuv-card{color:red}")
    t = {"type": "global-styles", "tokens": "tokens.json", "css": "c.css"}
    deploy._deploy_global_styles("global-styles", t, tmp_path, dry_run=False)
    assert captured["styles"]["css"] == ".stuv-card{color:red}"
    assert captured["styles"]["typography"]["fontFamily"] == "x"
    assert captured["confirm"] is True


def test_dir_source_joined_in_name_order(tmp_path):
    d = tmp_path / "sections"
    d.mkdir()
    (d / "02-b.html").write_text("zwei")
    (d / "01-a.html").write_text("eins")
    assert deploy._read_source(tmp_path, "sections") == "eins\n\nzwei"


def test_media_failure_does_not_pass_silently(tmp_path, monkeypatch, capsys):
    d = tmp_path / "img"
    d.mkdir()
    (d / "good.png").write_bytes(b"a")
    (d / "bad.png").write_bytes(b"b")
    uploaded = []

    def fake_upload(path, *, reuse_existing):
        if os.path.basename(path) == "bad.png":
            raise RuntimeError("413 payload too large")
        uploaded.append(os.path.basename(path))
        return {"id": 1, "source_url": "https://x/good.png"}

    monkeypatch.setattr(wp, "upload_media", fake_upload)
    t = {"type": "media", "source": "img"}
    with pytest.raises(RuntimeError, match="bad.png"):
        deploy._deploy_media("img", t, tmp_path, dry_run=False)
    assert uploaded == ["good.png"], "a later file must still upload after an earlier failure"


def test_media_dry_run_uploads_nothing(tmp_path, monkeypatch, capsys):
    d = tmp_path / "img"
    d.mkdir()
    (d / "logo.png").write_bytes(b"abc")

    def refuse(*a, **k):
        raise AssertionError("dry run must not upload")

    monkeypatch.setattr(wp, "upload_media", refuse)
    deploy._deploy_media("img", {"type": "media", "source": "img"}, tmp_path, dry_run=True)
    assert "[dry-run] upload logo.png (3 bytes)" in capsys.readouterr().out


def test_media_uploads_in_name_order_skipping_dotfiles(tmp_path, monkeypatch, capsys):
    d = tmp_path / "img"
    d.mkdir()
    (d / "02-b.png").write_bytes(b"b")
    (d / "01-a.png").write_bytes(b"a")
    (d / ".DS_Store").write_bytes(b"x")
    seen = []

    def fake_upload(path, *, reuse_existing):
        seen.append((os.path.basename(path), reuse_existing))
        return {"id": len(seen), "source_url": f"https://x/{os.path.basename(path)}"}

    monkeypatch.setattr(wp, "upload_media", fake_upload)
    deploy._deploy_media("img", {"type": "media", "source": "img"}, tmp_path, dry_run=False)
    assert seen == [("01-a.png", True), ("02-b.png", True)]


def test_media_source_must_be_a_directory(tmp_path):
    (tmp_path / "logo.png").write_bytes(b"a")
    with pytest.raises(FileNotFoundError, match="not a directory"):
        deploy._deploy_media("img", {"type": "media", "source": "logo.png"},
                             tmp_path, dry_run=False)


def test_main_resolves_sources_relative_to_manifest(tmp_path, capsys):
    (tmp_path / "page.html").write_text(BALANCED)
    manifest = {"kontakt": {"type": "structural", "endpoint": "pages",
                            "id": 39, "source": "page.html", "status": "publish"}}
    mpath = tmp_path / "manifest.json"
    mpath.write_text(json.dumps(manifest))
    deploy.main(["--manifest", str(mpath), "all", "--dry-run"])
    out = capsys.readouterr().out
    assert "[dry-run] pages/39 <- page.html" in out
    assert "balanced OK" in out
