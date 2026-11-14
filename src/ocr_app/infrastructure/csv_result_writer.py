from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Sequence

from ocr_app.domain.models import OcrResult


class CsvResultWriter:
    def __init__(self, output_directory: Path) -> None:
        self._output_directory = output_directory

    def write(self, results: Sequence[OcrResult]) -> Path:
        """ROI 결과를 UTF-8 BOM이 있는 CSV 파일에 저장한다.

        Args:
            results: 입력 순서대로 기록할 ROI 결과 목록.

        Returns:
            생성된 CSV 경로. 신뢰도는 백분율로 쓰며 누락·비정상 값은 빈 셀로 쓴다.
            출력 폴더를 자동 생성하고 파일 이름에 저장 시각을 포함한다.
        """
        self._output_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = self._output_directory / f"ocr_result_{timestamp}.csv"

        with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
            writer.writerow(("UI ID", "언어", "추출 문자열", "상태", "신뢰도"))
            for result in results:
                confidence = (
                    f"{result.confidence * 100:.2f}%"
                    if result.confidence is not None and math.isfinite(result.confidence)
                    else ""
                )
                writer.writerow(
                    (
                        result.ui_id,
                        result.language_code,
                        result.extracted_text,
                        result.status.value,
                        confidence,
                    )
                )

        return output_path
