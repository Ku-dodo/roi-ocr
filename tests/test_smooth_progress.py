from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QAbstractAnimation
from PySide6.QtWidgets import QApplication

from ocr_app.presentation.smooth_progress_bar import SmoothProgressBar


class SmoothProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.bar = SmoothProgressBar()
        self.addCleanup(self.bar.deleteLater)

    def test_ease_in_starts_slowly_and_reaches_real_target(self):
        self.bar.set_progress(0.8)
        self.assertEqual(0, self.bar.value())
        self.bar._animation.setCurrentTime(self.bar.DURATION_MS // 2)
        self.assertEqual(2000, self.bar.value())  # Half the time, a quarter of the distance.
        self.bar._animation.setCurrentTime(self.bar.DURATION_MS)
        self.assertEqual(8000, self.bar.value())

    def test_duplicate_or_older_progress_does_not_restart_or_reverse_animation(self):
        self.bar.set_progress(0.8)
        self.bar._animation.setCurrentTime(160)
        self.bar.set_progress(0.8)
        self.bar.set_progress(0.2)
        self.assertEqual(160, self.bar._animation.currentTime())
        self.assertEqual(8000, self.bar._animation.endValue())
        before = self.bar.value()
        self.bar.set_progress(1.0)
        self.assertEqual(before, self.bar._animation.startValue())
        self.bar._animation.setCurrentTime(self.bar.DURATION_MS)
        self.assertEqual(self.bar.maximum(), self.bar.value())

    def test_new_run_resets_previous_animation_and_busy_mode(self):
        self.bar.set_progress(1.0)
        self.bar._animation.setCurrentTime(160)
        self.bar.reset_progress(busy=True)
        self.assertEqual(QAbstractAnimation.State.Stopped, self.bar._animation.state())
        self.assertEqual((0, 0), (self.bar.minimum(), self.bar.maximum()))
        self.bar.set_progress(0.1)
        self.bar._animation.setCurrentTime(self.bar.DURATION_MS)
        self.assertEqual(1000, self.bar.value())
        self.bar.reset_progress()
        self.assertEqual(0, self.bar.value())
        self.assertEqual(QAbstractAnimation.State.Stopped, self.bar._animation.state())
