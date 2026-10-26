import json
import os
import subprocess

import pytest

import deploy
import wp_block_api as wp

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
    deploy._deploy_global_styles(t, tmp_path, dry_run=False)
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
        deploy._deploy_media(t, tmp_path, dry_run=False)
    assert uploaded == ["good.png"], "a later file must still upload after an earlier failure"


def test_media_dry_run_uploads_nothing(tmp_path, monkeypatch, capsys):
    d = tmp_path / "img"
    d.mkdir()
    (d / "logo.png").write_bytes(b"abc")

    def refuse(*a, **k):
        raise AssertionError("dry run must not upload")

    monkeypatch.setattr(wp, "upload_media", refuse)
    deploy._deploy_media({"type": "media", "source": "img"}, tmp_path, dry_run=True)
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
    deploy._deploy_media({"type": "media", "source": "img"}, tmp_path, dry_run=False)
    assert seen == [("01-a.png", True), ("02-b.png", True)]


def test_media_source_must_be_a_directory(tmp_path):
    (tmp_path / "logo.png").write_bytes(b"a")
    with pytest.raises(FileNotFoundError, match="not a directory"):
        deploy._deploy_media({"type": "media", "source": "logo.png"}, tmp_path, dry_run=False)


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


class FakeSite:
    """Pages by id, served the way fetch_raw returns them; a save changes them."""

    def __init__(self, monkeypatch, pages, accepts_writes=True):
        self.pages, self.saved = dict(pages), []
        monkeypatch.setattr(wp, "fetch_raw", lambda e, i: {
            "content": {"raw": self.pages[i]}, "status": "publish"})
        monkeypatch.setattr(wp, "backup", lambda e, i: None)

        def save(e, i, content, status, *, confirm):
            self.saved.append(i)
            if accepts_writes:
                self.pages[i] = content
        monkeypatch.setattr(wp, "save_structural", save)


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True,
    )


@pytest.fixture
def repo(tmp_path):
    """Three pages, each "Alt" in the first commit and "Hallo" now, plus media."""
    targets = {}
    for i, name in enumerate(["home", "about", "events"], start=1):
        (tmp_path / f"{name}.html").write_text(BALANCED.replace("Hallo", "Alt"))
        targets[name] = {"type": "structural", "endpoint": "pages", "id": i,
                         "source": f"{name}.html", "status": "publish"}
    targets["media"] = {"type": "media", "source": "img"}
    (tmp_path / "img").mkdir()
    (tmp_path / "manifest.json").write_text(json.dumps(targets))
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "alt")
    for name in ["home", "about", "events"]:
        (tmp_path / f"{name}.html").write_text(BALANCED)
    _git(tmp_path, "commit", "-q", "-am", "neu")
    return tmp_path


ALT, EDIT = BALANCED.replace("Hallo", "Alt"), BALANCED.replace("Hallo", "aus wp-admin")


def test_changed_deploys_what_is_behind_or_edited_and_media(repo, monkeypatch, capsys):
    site = FakeSite(monkeypatch, {1: BALANCED, 2: ALT, 3: EDIT})
    monkeypatch.setattr(deploy, "_deploy_media", lambda *a: None)
    deploy.main(["--manifest", str(repo / "manifest.json"), "changed", "--overwrite", "events"])
    assert site.saved == [2, 3], "home matches already; about is behind, events edited"
    out = capsys.readouterr().out
    assert "Deploying: about events media" in out
    assert out.count("verified: live matches") == 2


def test_deploy_refuses_a_wp_admin_edit_unless_overwrite(repo, monkeypatch):
    site = FakeSite(monkeypatch, {1: EDIT, 2: BALANCED, 3: BALANCED})
    m = str(repo / "manifest.json")
    for argv in (["home"], ["changed"], ["all"], ["home", "--overwrite", "about"]):
        with pytest.raises(SystemExit, match="--overwrite home"):
            deploy.main(["--manifest", m, *argv])
    assert site.saved == [], "a refusal comes before the first write"
    deploy.main(["--manifest", m, "home", "--overwrite"])
    assert site.saved == [1]


def test_overwrite_names_only_the_targets_it_lists(repo, monkeypatch):
    site = FakeSite(monkeypatch, {1: EDIT, 2: BALANCED, 3: EDIT})
    m = str(repo / "manifest.json")
    with pytest.raises(SystemExit, match="not deployed: events"):
        deploy.main(["--manifest", m, "home", "events", "--overwrite", "home"])
    deploy.main(["--manifest", m, "home", "events", "--overwrite", "home,events"])
    assert site.saved == [1, 3]


def test_a_write_the_site_does_not_serve_stops_the_run(repo, monkeypatch):
    site = FakeSite(monkeypatch, {1: ALT, 2: ALT, 3: ALT}, accepts_writes=False)
    with pytest.raises(SystemExit, match="home: live differs after the write"):
        deploy.main(["--manifest", str(repo / "manifest.json"), "changed"])
    assert site.saved == [1], "nothing after the failed target is written"


def test_global_styles_markers_are_checked_after_the_write(tmp_path, monkeypatch):
    (tmp_path / "tokens.json").write_text("{}")
    (tmp_path / "c.css").write_text(".stuv-card{color:red}")
    (tmp_path / "manifest.json").write_text(json.dumps({"global-styles": {
        "type": "global-styles", "tokens": "tokens.json", "css": "c.css",
        "markers": [".stuv-card", ".stuv-gone"]}}))
    live = {"styles": {"css": ""}}
    monkeypatch.setattr(wp, "get_global_styles", lambda *a, **k: live)

    def apply(settings, styles, *, confirm):
        live["styles"] = styles
        return {"id": 7}
    monkeypatch.setattr(wp, "apply_global_styles", apply)
    m = str(tmp_path / "manifest.json")
    with pytest.raises(SystemExit, match="custom CSS lost rules"):
        deploy.main(["--manifest", m, "global-styles", "--overwrite"])

    (tmp_path / "c.css").write_text(".stuv-card{} .stuv-gone{}")
    deploy.main(["--manifest", m, "global-styles", "--overwrite"])


def test_unknown_names_and_mixed_selectors_are_rejected(repo):
    m = str(repo / "manifest.json")
    with pytest.raises(SystemExit, match="unknown target 'nope'"):
        deploy.main(["--manifest", m, "home", "--overwrite", "nope"])
    with pytest.raises(SystemExit):
        deploy.main(["--manifest", m, "changed", "home"])
