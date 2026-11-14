from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ocr_app.domain.models import Roi
from ocr_app.infrastructure.easyocr_roi_detector import EasyOcrRoiDetector
from ocr_app.infrastructure.image_loader import OpenCvImageLoader


class RoiDetectionSignals(QObject):
    """finished로 ROI 튜플을, failed로 오류 메시지를 UI 스레드에 전달한다."""
    finished = Signal(object)
    failed = Signal(str)


class RoiDetectionWorker(QRunnable):
    def __init__(self, path: Path, models: Path, existing: tuple[Roi, ...], allow_download: bool):
        """백그라운드 검출 작업에 필요한 입력과 결과 신호를 준비한다.

        Args:
            path: 검출할 원본 이미지 파일 경로.
            models: EasyOCR 검출 모델 폴더.
            existing: 후보에서 제외할 기존 영역과 보존할 Tag·색상 정보.
            allow_download: 검출 모델 다운로드 허용 여부.

        Returns:
            None. 실제 이미지 로드와 검출은 run 호출 시 수행한다.
        """
        super().__init__()
        self.signals = RoiDetectionSignals()
        self._path, self._models = path, models
        self._existing, self._allow_download = existing, allow_download

    @Slot()
    def run(self) -> None:
        """별도 인자 없이 저장된 입력으로 이미지를 읽고 ROI 후보를 검출한다.

        Returns:
            None. 성공 시 finished 신호에 ROI 튜플을 담아 보내고,
            실패 시 failed 신호에 오류 메시지를 담아 보낸다.
        """
        try:
            image = OpenCvImageLoader().load(self._path)
            detector = EasyOcrRoiDetector(self._models, self._allow_download)
            self.signals.finished.emit(detector.detect(image, self._existing))
        except Exception as error:
            self.signals.failed.emit(str(error))
