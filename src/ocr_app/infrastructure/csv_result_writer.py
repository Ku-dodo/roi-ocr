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
