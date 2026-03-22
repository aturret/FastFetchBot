import sys
from pathlib import Path

# Add the async-worker app directory to sys.path so 'async_worker' is importable
_app_dir = Path(__file__).resolve().parents[3] / "apps" / "async-worker"
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))
