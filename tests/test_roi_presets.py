from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr_app.domain.models import Roi
from ocr_app.infrastructure.roi_preset_store import RoiPresetStore


class RoiPresetTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "presets" / "roi_presets.json"
        self.store = RoiPresetStore(self.path)
        self.rois = (Roi(10, 20, 100, 40, "user_name", "#45a3ff"),
                     Roi(10, 80, 100, 40, "password", "#ffb347"))

    def test_presets_persist_overwrite_and_delete_independently(self):
        self.store.save("Login_Scene", self.rois)
        self.store.save("메인 화면", self.rois[:1])
        restored = RoiPresetStore(self.path)
        self.assertEqual(self.rois, restored.load("Login_Scene"))
        restored.save("Login_Scene", self.rois[1:])
        self.assertEqual(self.rois[1:], self.store.load("Login_Scene"))
        restored.delete("Login_Scene")
        self.assertEqual(["메인 화면"], self.store.names())
        self.assertEqual(self.rois[:1], self.store.load("메인 화면"))

    def test_invalid_or_corrupt_presets_do_not_overwrite_existing_file(self):
        self.store.save("Login_Scene", self.rois)
        before = self.path.read_bytes()
        invalid_sets = ((), (Roi(0, 0, 1, 1),), (self.rois[0], self.rois[0]),
                        (Roi(0, 0, 1, 1, "id", "invalid"),))
        for rois in invalid_sets:
            with self.subTest(rois=rois), self.assertRaises(ValueError):
                self.store.save("Invalid", rois)
            self.assertEqual(before, self.path.read_bytes())
        self.path.write_text("invalid json", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.save("New", self.rois)
        self.assertEqual("invalid json", self.path.read_text(encoding="utf-8"))

    def test_failed_atomic_replace_preserves_existing_presets(self):
        self.store.save("Login_Scene", self.rois)
        before = self.path.read_bytes()
        with patch("ocr_app.infrastructure.roi_preset_store.os.replace", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                self.store.save("New", self.rois)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([self.path], list(self.path.parent.iterdir()))

    def test_invalid_roi_geometry_in_file_is_rejected(self):
        self.store.save("Login_Scene", self.rois)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["presets"]["Login_Scene"][0]["width"] = 0
        self.path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.load("Login_Scene")
