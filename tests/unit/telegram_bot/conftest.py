import sys
from pathlib import Path

# Add the telegram-bot app directory to sys.path so 'core' is importable
_app_dir = Path(__file__).resolve().parents[3] / "apps" / "telegram-bot"
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))
