from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QProgressBar


class SmoothProgressBar(QProgressBar):
    SCALE = 10000
    DURATION_MS = 320

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._target = 0
        self._animation = QPropertyAnimation(self, b"value", self)
        self._animation.setDuration(self.DURATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.InQuad)
        self.reset_progress()

    def reset_progress(self, *, busy: bool = False) -> None:
        self._animation.stop()
        self._target = 0
        self.setRange(0, 0 if busy else self.SCALE)
        self.setValue(0)

    def set_progress(self, fraction: float) -> None:
        if self.maximum() == 0:
            self.reset_progress()
        target = round(max(0.0, min(1.0, fraction)) * self.SCALE)
        # Repeated callbacks must not restart an animation or move it backwards.
        if target <= self._target:
            return
        self._target = target
        self._animation.stop()
        self._animation.setStartValue(max(0, self.value()))
        self._animation.setEndValue(target)
        self._animation.start()
