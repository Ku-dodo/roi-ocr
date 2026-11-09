# Third-party software notices

이 프로그램은 아래 제3자 소프트웨어를 포함하거나 사용합니다. 이 문서는 요약이며,
각 라이선스의 영문 원문이 우선합니다. 전체 수집 자료는 `licenses/generated/`, 직접
관리하는 공통 라이선스 전문과 고지는 `licenses/manual/`에 있습니다.

## 핵심 런타임 구성요소

| 구성요소 | 현재 버전 | 라이선스 | 배포 시 핵심 사항 |
|---|---:|---|---|
| Python | 3.13.17 | PSF License v2 및 동봉 라이선스 | Python 라이선스와 저작권 고지 포함 |
| PySide6 Essentials | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only / 상용 | 커뮤니티 wheel 사용 시 폐쇄형 배포는 LGPLv3 조건을 충족하거나 Qt 상용 라이선스 필요 |
| Shiboken6 | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only / 상용 | PySide6와 동일한 Qt 배포 검토 대상 |
| python-bidi | 0.6.12 | LGPL, 배포 파일에는 LGPLv3 전문 포함 | LGPL/GPL 전문과 고지 포함, 수정 라이브러리 교체 허용 |
| EasyOCR | 1.7.2 | Apache License 2.0 | 저작권·라이선스·NOTICE 유지, 모델은 아래 별도 검토 |
| OpenCV | 4.14.0.94 | Apache License 2.0 및 동봉 제3자 라이선스 | 라이선스와 NOTICE 유지 |
| PyTorch | 2.15.0+cpu | BSD-3-Clause 중심의 복합 제3자 라이선스 | wheel에 포함된 모든 제3자 고지 유지 |
| Torchvision | 0.29.2+cpu | BSD 계열 및 동봉 제3자 라이선스 | 라이선스 고지 유지 |
| NumPy | 2.5.4 | BSD-3-Clause 및 동봉 제3자 라이선스 | wheel의 전체 라이선스 묶음 유지 |
| SciPy | 1.18.1 | BSD 계열 및 동봉 제3자 라이선스 | wheel의 전체 라이선스 묶음 유지 |
| scikit-image | 0.26.0 | BSD-3-Clause/BSD-2-Clause/MIT | 동봉 저작권과 라이선스 유지 |

## 그 밖의 런타임 의존성

ImageIO(BSD-2-Clause), Pillow(MIT-CMU), Shapely(BSD-3-Clause),
Tifffile(BSD-3-Clause), PyYAML(MIT), Jinja2(BSD-3-Clause),
MarkupSafe(BSD-3-Clause), NetworkX(BSD-3-Clause), Fsspec(BSD-3-Clause),
Filelock(MIT), Pyclipper(MIT), SymPy(BSD), Mpmath(BSD),
Typing Extensions(PSF-2.0), Packaging(Apache-2.0 OR BSD-2-Clause) 등이
포함됩니다. 정확한 버전과 원문은 `licenses/generated/INSTALLED_PACKAGES.txt` 및
각 패키지 하위 폴더를 참조하십시오.

## 빌드 도구

PyInstaller 6.22.3은 `GPL-2.0-or-later WITH Bootloader-exception`입니다.
Bootloader Exception에 따라 생성된 실행 파일을 독점 또는 상용 프로그램으로 배포할
수 있습니다. PyInstaller 자체나 수정한 빌드 도구를 별도로 배포하는 경우에는 해당
GPL 조건을 다시 검토해야 합니다.

## OCR 모델

배포본에는 EasyOCR 사전 학습 모델 파일을 포함하지 않습니다. 필요한 모델은 사용자가
첫 OCR 실행 시 EasyOCR의 공식 다운로드 위치에서 직접 받으며, `models/` 폴더는 이때
자동으로 생성됩니다. 모델 파일을 배포본에 추가하는 경우에는 별도 라이선스 검토가
필요합니다.

## Qt LGPLv3 배포

현재 `onedir` 결과물은 Qt DLL을 `_internal/` 아래의 독립 파일로 동적 로드합니다.
Qt/PySide6/Shiboken6에는 LGPLv3가 적용되며, 영문 전문과 고지는
`licenses/manual/`에 포함되어 있습니다.
