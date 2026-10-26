#!/usr/bin/env python3
"""Compare the plugins installed on the live site (presence, status, version) with wp-plugin/.

Needs admin credentials. Exit codes: 0 all match, 1 some differ, 2 list not fetched.

    python3 tools/check_plugins.py
"""

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
PLUGINS = REPO / "wp-plugin"
SKILL_SCRIPTS = REPO / ".agents" / "skills" / "wordpress-default-editor" / "scripts"

HEADER_VERSION_RE = re.compile(r"^\s*\*\s*Version:\s*(\S+)", re.MULTILINE)
CONSTANT_VERSION_RE = re.compile(r"define\('STUV_[A-Z]+_VERSION',\s*'([^']+)'\)")


def local_plugins():
    """{name: (header version, constant version or None)} for every plugin in wp-plugin/."""
    found = {}
    for main in sorted(PLUGINS.glob("*/*.php")):
        if main.stem != main.parent.name:
            continue
        text = main.read_text()
        header = HEADER_VERSION_RE.search(text)
        constant = CONSTANT_VERSION_RE.search(text)
        found[main.stem] = (
            header.group(1) if header else None,
            constant.group(1) if constant else None,
        )
    return found


def compare(local, live):
    """[(name, problem)] for each plugin in `local`; problem is None when it matches."""
    by_dir = {p["plugin"].split("/")[0]: p for p in live}
    result = []
    for name, version in sorted(local.items()):
        p = by_dir.get(name)
        if p is None:
            problem = f"not installed (repo {version})"
        elif p.get("status") != "active":
            problem = f"{p.get('status')} (repo {version})"
        elif p.get("version") != version:
            problem = f"live {p.get('version')}, repo {version}"
        else:
            problem = None
        result.append((name, problem))
    return result


def main():
    sys.path.insert(0, str(SKILL_SCRIPTS))
    import wp_block_api as wp

    local = {name: header for name, (header, _) in local_plugins().items()}
    try:
        # The client has no public call for this route; _request carries the
        # auth, retries and the IPv4 fallback the host needs.
        live = wp._request("GET", "plugins?_fields=plugin,status,version")
    except Exception as exc:  # noqa: BLE001 - any failure means "could not check"
        print(f"could not fetch the plugin list: {exc}", file=sys.stderr)
        return 2
    bad = 0
    for name, problem in compare(local, live):
        print(f"DIFFERS {name}: {problem}" if problem else f"OK      {name} {local[name]}")
        bad += problem is not None
    if bad:
        print("Build the zip (wp-plugin/build.sh) and upload it in wp-admin: docs/plugins.md.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
