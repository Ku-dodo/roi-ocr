from __future__ import annotations

import sys
from pathlib import Path


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def result_directory() -> Path:
    return application_directory() / "result"


def model_directory() -> Path:
    return application_directory() / "models"
