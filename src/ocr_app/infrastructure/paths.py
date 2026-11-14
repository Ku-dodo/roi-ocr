from __future__ import annotations

import sys
from pathlib import Path


def application_directory() -> Path:
    """별도 입력 없이 실행 형태에 맞는 사용자 데이터 기준 폴더를 반환한다.

    Returns:
        패키징한 앱에서는 EXE가 있는 폴더, 소스 실행에서는 프로젝트 루트.
        PyInstaller 내부 리소스 폴더와 구별하여 모델·결과를 이 위치에 저장한다.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def result_directory() -> Path:
    return application_directory() / "result"


def model_directory() -> Path:
    return application_directory() / "models"
