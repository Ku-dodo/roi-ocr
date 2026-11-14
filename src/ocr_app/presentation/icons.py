from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


ASSET_DIRECTORY = Path(__file__).with_name("assets")


def svg_icon(name: str) -> QIcon:
    """앱의 SVG 리소스를 여러 크기로 렌더링하여 Qt 아이콘을 만든다.

    Args:
        name: assets 폴더 안의 SVG 파일 이름. 예: app.svg, auto-roi.svg.

    Returns:
        16~256픽셀의 렌더링 결과를 담은 QIcon. 호출 전에 QApplication이 필요하다.
    """
    renderer = QSvgRenderer(str(ASSET_DIRECTORY / name))
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon
