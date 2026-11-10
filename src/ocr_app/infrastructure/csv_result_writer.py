from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Sequence

from ocr_app.domain.models import OcrResult


class CsvResultWriter:
    def __init__(self, output_directory: Path, include_file_extension: bool = True) -> None:
        self._output_directory = output_directory
        self._include_file_extension = include_file_extension

    def write(self, results: Sequence[OcrResult]) -> Path:
        self._output_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = self._output_directory / f"ocr_result_{timestamp}.csv"

        with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
            writer.writerow(("파일 이름", "추출 문자열", "정확도(신뢰도)"))
            for result in results:
                file_name = (
                    result.file_name
                    if self._include_file_extension
                    else Path(result.file_name).stem
                )
                confidence = (
                    f"{result.confidence * 100:.2f}%"
                    if result.confidence is not None
                    else ""
                )
                writer.writerow(
                    (file_name, result.extracted_text, confidence)
                )

        return output_path
