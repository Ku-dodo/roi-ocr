from __future__ import annotations

import csv
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
            writer.writerow(("파일 이름", "추출 문자열", "정확도(신뢰도)"))
            for result in results:
                confidence = (
                    f"{result.confidence * 100:.2f}%"
                    if result.confidence is not None
                    else ""
                )
                writer.writerow(
                    (result.file_name, result.extracted_text, confidence)
                )

        return output_path
