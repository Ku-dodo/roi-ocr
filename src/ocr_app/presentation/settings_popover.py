from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QTimer, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QWidget


class SettingsPopover(QFrame):
    """A hover panel that stays open while its controls or combo popup are in use."""

    def __init__(self, anchor: QPushButton, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("settingsPopover")
        self._anchor = anchor
        self._open_timer = QTimer(self)
        self._open_timer.setSingleShot(True)
        self._open_timer.setInterval(180)
        self._open_timer.timeout.connect(self.show_panel)
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.setInterval(300)
        self._close_timer.timeout.connect(self._close_if_outside)
        anchor.clicked.connect(self.show_panel)
        QApplication.instance().installEventFilter(self)
        self.hide()

    def show_panel(self) -> None:
        if not self._anchor.isEnabled() or not self._anchor.isVisible():
            return
        self._open_timer.stop()
        self._close_timer.stop()
        self.adjustSize()
        parent = self.parentWidget()
        position = self._anchor.mapTo(parent, QPoint(self._anchor.width(), self._anchor.height() + 6))
        x = max(8, min(position.x() - self.width(), parent.width() - self.width() - 8))
        y = position.y()
        if y + self.height() > parent.height() - 8:
            y = max(8, self._anchor.mapTo(parent, QPoint()).y() - self.height() - 6)
        self.move(x, y)
        self.show()
        self.raise_()

    def hide_panel(self) -> None:
        self._open_timer.stop()
        self._close_timer.stop()
        self.hide()

    def _contains_position(self, position: QPoint) -> bool:
        return any(
            widget.rect().contains(widget.mapFromGlobal(position))
            for widget in (self, self._anchor)
        )

    def _close_if_outside(self) -> None:
        """커서가 패널 밖에 있어도 콤보 목록이 열려 있으면 닫기를 미룬다.

        Returns:
            None. 입력 인자는 없으며, 현재 팝업과 전역 커서 위치를 검사한다.
        """
        if QApplication.activePopupWidget() is not None:
            # A combo box dropdown is a separate window; let the user finish selecting.
            self._close_timer.start()
        elif not self._contains_position(QCursor.pos()):
            self.hide_panel()

    def eventFilter(self, watched, event) -> bool:
        """앱 이벤트를 관찰하여 설정 패널의 지연 열기·닫기와 Escape를 처리한다.

        Args:
            watched: 이벤트가 발생한 Qt 객체.
            event: 진입·이탈·이동·클릭·키 입력 등 Qt 이벤트.

        Returns:
            패널이 처리한 Escape이면 True. 나머지는 기본 필터에 위임한다.
            콤보 팝업이 열린 동안에는 외부 클릭에 의한 자동 닫기를 보류한다.
        """
        kind = event.type()
        if watched is self._anchor or watched is self:
            if kind == QEvent.Type.Enter:
                self._close_timer.stop()
                if watched is self._anchor and self._anchor.isEnabled() and not self.isVisible():
                    self._open_timer.start()
            elif kind == QEvent.Type.Leave:
                self._open_timer.stop()
                self._close_timer.start()

        if watched is self.parentWidget() and kind in (
            QEvent.Type.Hide, QEvent.Type.Move, QEvent.Type.Resize,
        ):
            self.hide_panel()
        if self.isVisible() and QApplication.activePopupWidget() is None:
            if kind == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.hide_panel()
                self._anchor.setFocus()
                return True
            if kind == QEvent.Type.MouseButtonPress:
                position = event.globalPosition().toPoint()
                if not self._contains_position(position):
                    self.hide_panel()
            if kind == QEvent.Type.ApplicationDeactivate:
                self.hide_panel()
        return super().eventFilter(watched, event)
