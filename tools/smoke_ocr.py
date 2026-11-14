from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ocr_app.application.process_images import ProcessImagesUseCase
from ocr_app.domain.models import ImageItem
from ocr_app.infrastructure.csv_result_writer import CsvResultWriter
from ocr_app.infrastructure.easyocr_engine import EasyOcrEngine
from ocr_app.infrastructure.opencv_processor import OpenCvImageProcessor


def main() -> int:
    """명령행 이미지 한 장으로 실제 전처리·OCR·CSV 저장 경로를 점검한다.

    Returns:
        이미지 처리 실패가 없으면 종료 코드 0, 실패가 있으면 1.
        입력 경로는 명령행에서 받으며 모델 다운로드를 허용하고 결과 위치를 출력한다.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="한 이미지로 실제 OCR 파이프라인을 점검합니다.")
    parser.add_argument("image", type=Path)
    arguments = parser.parse_args()

    item = ImageItem(arguments.image, scale_factor=2)
    use_case = ProcessImagesUseCase(
        image_processor=OpenCvImageProcessor(),
        ocr_engine=EasyOcrEngine(
            PROJECT_ROOT / "models",
            languages=("ko", "en"),
            use_gpu=False,
            allow_download=True,
        ),
        result_writer=CsvResultWriter(PROJECT_ROOT / "result"),
    )
    summary = use_case.execute([item])
    print(f"status={item.status.value}")
    print(f"text={item.extracted_text}")
    print(f"csv={summary.output_path}")
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
