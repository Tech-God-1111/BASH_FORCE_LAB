"""Central project paths used by every module."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
BASH_DIR = ROOT / "bash"
DATA_DIR = ROOT / "data"
FRONTEND_DIR = ROOT / "frontend"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "activity.log"
REPORT_DIR = ROOT / "reports"
CONFIG_FILE = ROOT / "config.json"
PHONE_STATE_FILE = DATA_DIR / "virtual_phone.json"
