from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def run_ocr_smoke_test(image_path: Path) -> int:
    """GUI 없이 실제 OCR을 실행하여 소스·패키징 환경의 동작을 점검한다.

    Args:
        image_path: 한국어·영어 모델로 처리할 이미지 경로.

    Returns:
        처리 실패가 없으면 0, 실패가 있으면 1. 모델 다운로드를 허용하며
        전체 이미지를 2배로 확대해 앱의 결과 폴더에 CSV를 저장한다.
    """
    from ocr_app.application.process_images import ProcessImagesUseCase
    from ocr_app.domain.models import ImageItem
    from ocr_app.infrastructure.csv_result_writer import CsvResultWriter
    from ocr_app.infrastructure.easyocr_engine import EasyOcrEngine
    from ocr_app.infrastructure.opencv_processor import OpenCvImageProcessor
    from ocr_app.infrastructure.paths import model_directory, result_directory

    item = ImageItem(image_path, scale_factor=2)
    use_case = ProcessImagesUseCase(
        image_processor=OpenCvImageProcessor(),
        ocr_engine=EasyOcrEngine(
            model_directory(),
            languages=("ko", "en"),
            use_gpu=False,
            allow_download=True,
        ),
        result_writer=CsvResultWriter(result_directory()),
    )
    summary = use_case.execute([item])
    return 0 if summary.failed == 0 else 1


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-ocr":
        return run_ocr_smoke_test(Path(sys.argv[2]))

    from PySide6.QtWidgets import QApplication

    from ocr_app.presentation.main_window import MainWindow
    from ocr_app.presentation.icons import svg_icon

    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Internal.ROI.OCRTool")

    app = QApplication(sys.argv)
    app.setApplicationName("이미지 OCR 도구")
    app.setOrganizationName("Internal")
    app.setWindowIcon(svg_icon("app.svg"))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
