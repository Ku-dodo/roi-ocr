from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import tempfile

from ocr_app.domain.models import Roi


class RoiPresetStore:
    """Store named ROI sets, excluding images, language choices and OCR results."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @staticmethod
    def _decode(entries: object) -> tuple[Roi, ...]:
        """JSON에서 읽은 ROI 항목의 타입·Tag·색상·중복을 검증한다.

        Args:
            entries: ROI 딕셔너리의 비어 있지 않은 목록이어야 하는 역직렬화 값.

        Returns:
            검증된 ROI 튜플. 잘못된 타입, 빈 Tag, 중복 Tag 등은 ValueError로 알린다.
        """
        if not isinstance(entries, list) or not entries:
            raise ValueError("프리셋에는 ROI가 하나 이상 필요합니다.")
        rois = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("올바르지 않은 ROI 정보입니다.")
            if any(type(entry.get(key)) is not int for key in ("x", "y", "width", "height")):
                raise ValueError("ROI 좌표와 크기는 정수여야 합니다.")
            tag, color = entry.get("tag"), entry.get("color")
            if not isinstance(tag, str) or not tag.strip() or tag != tag.strip():
                raise ValueError("ROI Tag가 비어 있거나 올바르지 않습니다.")
            if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("올바르지 않은 ROI 색상입니다.")
            rois.append(Roi(**{key: entry[key] for key in ("x", "y", "width", "height", "tag", "color")}))
        if len({roi.tag for roi in rois}) != len(rois):
            raise ValueError("ROI Tag가 중복됩니다.")
        return tuple(rois)

    def _read(self) -> dict[str, tuple[Roi, ...]]:
        """입력 인자 없이 파일 형식 버전과 전체 프리셋 내용을 검사하여 읽는다.

        Returns:
            이름을 키로 하는 ROI 튜플 사전. 파일이 아직 없으면 빈 사전이며,
            손상되거나 지원하지 않는 형식의 파일은 예외를 전파한다.
        """
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("presets"), dict):
                raise ValueError("지원하지 않는 프리셋 파일 형식입니다.")
            if any(not isinstance(name, str) or not name.strip() for name in data["presets"]):
                raise ValueError("올바르지 않은 프리셋 이름입니다.")
            return {name: self._decode(entries) for name, entries in data["presets"].items()}
        except (TypeError, KeyError) as error:
            raise ValueError("프리셋 파일을 읽을 수 없습니다.") from error

    def names(self) -> list[str]:
        return sorted(self._read(), key=str.casefold)

    def load(self, name: str) -> tuple[Roi, ...]:
        try:
            return self._read()[name]
        except KeyError as error:
            raise ValueError("선택한 프리셋이 없습니다.") from error

    def save(self, name: str, rois: tuple[Roi, ...]) -> None:
        """ROI를 검증하고 이름의 양끝 공백을 제거하여 프리셋을 저장한다.

        Args:
            name: 프리셋 이름. 같은 이름이 있으면 해당 항목을 덮어쓴다.
            rois: 저장할 비어 있지 않은 ROI 튜플.

        Returns:
            None. 다른 프리셋은 유지한다. 검증·파일 저장 오류는 호출자에게 전파한다.
        """
        if not name.strip():
            raise ValueError("프리셋 이름을 입력해 주세요.")
        validated = self._decode([asdict(roi) for roi in rois])
        presets = self._read()
        presets[name.strip()] = validated
        self._write(presets)

    def delete(self, name: str) -> None:
        presets = self._read()
        if name not in presets:
            raise ValueError("선택한 프리셋이 없습니다.")
        del presets[name]
        self._write(presets)

    def _write(self, presets: dict[str, tuple[Roi, ...]]) -> None:
        """임시 파일을 완성한 뒤 교체하여 중간 저장으로 인한 파일 손상을 줄인다.

        Args:
            presets: 파일에 기록할 전체 프리셋 사전.

        Returns:
            None. 버전 1 JSON으로 저장하고 실패 시에도 남은 임시 파일을 정리한다.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "presets": {name: [asdict(roi) for roi in rois] for name, rois in presets.items()}}
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as stream:
                temporary_path = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2)
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
