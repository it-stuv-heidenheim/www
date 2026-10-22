
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import scripts.verify_global_css as verify
import scripts.wp_block_api as wp

MARKER_ARGS = ["--marker", ".stuv-card", "--marker", ".stuv-icon-box",
               "--icon-marker=--ico-calendar"]

CSS_ALL_INTACT = (
    ".stuv-card{color:red} .stuv-icon-box{display:flex} "
    ":root{--ico-calendar:url('data:image/svg+xml,<svg/>')}"
)
CSS_ICONS_STRIPPED = ".stuv-card{color:red} .stuv-icon-box{display:flex}"
CSS_RULES_MISSING = (
    ".stuv-icon-box{display:flex} "
    ":root{--ico-calendar:url('data:image/svg+xml,<svg/>')}"
)


def _run(monkeypatch, css, argv=MARKER_ARGS):
    monkeypatch.setattr(wp, "get_global_styles",
                        lambda gid=None: {"styles": {"css": css}})
    return verify.main(argv)


def test_all_intact_exits_0(monkeypatch):
    assert _run(monkeypatch, CSS_ALL_INTACT) == 0


def test_icon_uri_stripped_exits_2(monkeypatch):
    assert _run(monkeypatch, CSS_ICONS_STRIPPED) == 2


def test_marker_missing_exits_1(monkeypatch):
    assert _run(monkeypatch, CSS_RULES_MISSING) == 1


def test_no_icon_marker_skips_icon_check(monkeypatch):
    assert _run(monkeypatch, CSS_ICONS_STRIPPED,
                ["--marker", ".stuv-card"]) == 0
