#!/usr/bin/env python3
"""
Verify the mock server log for an eval run.
Usage: python3 evals/check_eval.py
"""
import json
import sys


def main():
    log_path = "/tmp/wp_mock_server.log"
    try:
        with open(log_path, encoding="utf-8") as f:
            log = f.read()
    except FileNotFoundError:
        print(json.dumps({"error": "server log not found"}, indent=2))
        sys.exit(1)

    checks = {
        "used_basic_auth": "Authorization: Basic" in log,
        "fetched_with_context_edit": "context=edit" in log,
        "posted_content": "POST /wp-json/wp/v2/pages/" in log,
        "posted_status": '"status"' in log or "status=" in log,
    }
    print(json.dumps(checks, indent=2))
    if not all(checks.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
