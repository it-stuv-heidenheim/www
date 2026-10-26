import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

# Overwrite, never setdefault: a sourced .env would point the writing tests at the real site.
os.environ["WP_USER"] = "test"
os.environ["WP_APP_PASS"] = "pass"
os.environ["WP_SITE"] = "http://127.0.0.1:5001"
for var in ("WP_REST_ROOT", "WP_ADDRESS_FAMILY", "WP_CONNECT_TIMEOUT"):
    os.environ.pop(var, None)
