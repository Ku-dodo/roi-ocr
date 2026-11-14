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
        """진행률을 0~1로 제한하고 이전 목표보다 증가한 경우에만 애니메이션한다.

        Args:
            fraction: 전체 작업 중 완료한 비율. 백분율이 아닌 0~1 기준이다.

        Returns:
            None. 대기 표시를 일반 진행률로 전환하며, 중복·역방향 갱신은 무시한다.
            새 작업의 0% 초기화는 reset_progress로 수행한다.
        """
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
