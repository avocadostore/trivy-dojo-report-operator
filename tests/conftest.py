import os
import sys
from pathlib import Path

# handlers.py / settings.py / env_vars.py live as flat, non-package modules under src/
# (they are copied flat into /app in the container image and imported bare, e.g.
# `import settings`), so tests need src/ on sys.path rather than importing them as a
# package.
SRC_PATH = str(Path(__file__).resolve().parent.parent / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# settings.py requires these at import time (get_required_env_var exits the process if
# missing), so they must be set before anything imports `handlers` or `settings`.
os.environ.setdefault("DEFECT_DOJO_API_KEY", "test-api-key")
os.environ.setdefault("DEFECT_DOJO_URL", "https://defectdojo.example.test")
