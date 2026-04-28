"""Project configuration values for file-system paths."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = (PROJECT_ROOT / "data").resolve()
DATA_RAW_DIR = (DATA_DIR / "raw").resolve()
DATA_PROCESSED_DIR = (DATA_DIR / "processed").resolve()
DATA_OUTPUTS_DIR = (DATA_DIR / "outputs").resolve()
APP_DIR = (PROJECT_ROOT / "app").resolve()

# Backward-compatible aliases for existing references.
RAW_DIR = DATA_RAW_DIR
PROCESSED_DIR = DATA_PROCESSED_DIR
OUTPUTS_DIR = DATA_OUTPUTS_DIR
