"""Load config.yaml và export CONFIG + các path thông dụng."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
FRONTEND_DIR = ROOT / "frontend"

_cfg_path = ROOT / "config.yaml"

with open(_cfg_path, encoding="utf-8") as f:
    CONFIG: dict = yaml.safe_load(f)

# Đảm bảo các thư mục tồn tại
for _d in [
    DATA_DIR / "cv",
    DATA_DIR / "knowledge",
    DATA_DIR / "questions",
    DATA_DIR / "memory" / "journal",
    DATA_DIR / "sessions",
]:
    _d.mkdir(parents=True, exist_ok=True)
