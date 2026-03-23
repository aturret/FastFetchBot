import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add the async-worker app directory to sys.path so 'async_worker' is importable
_app_dir = Path(__file__).resolve().parents[3] / "apps" / "async-worker"
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))

# Pre-mock async_worker.celery_client to avoid Celery trying to connect to Redis
# during test collection and lazy imports in enrichment.py
_mock_celery_module = MagicMock()
_mock_celery_module.celery_app = MagicMock()
sys.modules.setdefault("async_worker.celery_client", _mock_celery_module)
