"""Render the source SVG as a multi-resolution Windows executable icon."""
from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication


def main() -> None:
    app = QApplication.instance() or QApplication([])
    assets = Path(__file__).resolve().parents[1] / "src" / "ocr_app" / "presentation" / "assets"
    renderer = QSvgRenderer(str(assets / "app.svg"))
    if not renderer.isValid():
        raise ValueError("Invalid application SVG")
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    Image.open(io.BytesIO(bytes(data))).save(
        assets / "app.ico", sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)]
    )
    print(assets / "app.ico")


if __name__ == "__main__":
    main()
