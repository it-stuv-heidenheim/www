import os
import sys

# The scripts import each other as top-level modules, as they do when run.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

# Overwrite, never setdefault: a shell that has sourced a site's .env would
# otherwise point the server-backed tests, which write pages and global styles,
# at the real site with real credentials.
os.environ["WP_USER"] = "test"
os.environ["WP_APP_PASS"] = "pass"
os.environ["WP_SITE"] = "http://127.0.0.1:5001"
for var in ("WP_REST_ROOT", "WP_ADDRESS_FAMILY", "WP_CONNECT_TIMEOUT"):
    os.environ.pop(var, None)
