from __future__ import annotations

import re
import shutil
import sys
from importlib import metadata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "licenses" / "generated"
NOTICE_PATH = OUTPUT_ROOT / "INSTALLED_PACKAGES.txt"
LICENSE_NAMES = ("license", "copying", "notice", "copyright")


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    notice_lines = [
        "Installed Python packages and declared licenses",
        "================================================",
        "",
    ]

    distributions = sorted(
        metadata.distributions(),
        key=lambda distribution: (distribution.metadata.get("Name") or "").casefold(),
    )
    for distribution in distributions:
        package_name = distribution.metadata.get("Name") or "unknown"
        version = distribution.version
        license_value = (
            distribution.metadata.get("License-Expression")
            or distribution.metadata.get("License")
            or "검토 필요"
        )
        home_page = distribution.metadata.get("Home-page") or ""
        notice_lines.append(f"{package_name} {version}")
        notice_lines.append(f"  License: {license_value}")
        if home_page:
            notice_lines.append(f"  Home-page: {home_page}")

        package_output = OUTPUT_ROOT / safe_name(f"{package_name}-{version}")
        copied = 0
        for relative_file in distribution.files or ():
            base_name = Path(str(relative_file)).name.casefold()
            if not any(token in base_name for token in LICENSE_NAMES):
                continue
            source = Path(distribution.locate_file(relative_file))
            if not source.is_file():
                continue
            package_output.mkdir(parents=True, exist_ok=True)
            destination = package_output / source.name
            if destination.exists():
                destination = package_output / f"{copied}_{source.name}"
            shutil.copy2(source, destination)
            copied += 1
        notice_lines.append(f"  License files copied: {copied}")
        notice_lines.append("")

    NOTICE_PATH.write_text("\n".join(notice_lines), encoding="utf-8")
    print(f"License materials collected: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
