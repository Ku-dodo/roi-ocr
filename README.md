# 이미지 OCR 도구

여러 이미지에 하나의 Static ROI를 일괄 적용하고 최대 4배로 확대하여 EasyOCR로 문자열을 추출하는 Windows 데스크톱 프로그램입니다. 결과는 실행 파일 위치의 `result/` 폴더에 CSV로 저장됩니다.

## 개발 환경 준비

Python 3.10 환경에서 검증했습니다. CPU 전용 PyTorch를 먼저 설치하여 CUDA 라이브러리가 배포물에 들어가지 않도록 합니다.

```powershell
python -m venv .venv-release
.\.venv-release\Scripts\python.exe -m pip install --upgrade pip
.\.venv-release\Scripts\python.exe -m pip install torch==2.14.1+cpu torchvision==0.29.2+cpu --index-url https://download.pytorch.org/whl/cpu
.\.venv-release\Scripts\python.exe -m pip install -r requirements.txt
```

선택한 언어 모델이 없으면 상단 톱니바퀴 설정에서 `모델 자동 다운로드`를 체크한 뒤 OCR을 실행해 `models/` 폴더로 다운로드할 수 있습니다. 이 옵션의 기본값은 꺼짐입니다. 배포본에도 모델 파일은 포함하지 않으므로 모델을 내려받을 때 인터넷 연결이 필요합니다.

## 실행

```powershell
.\.venv-release\Scripts\python.exe .\main.py
```

1. `이미지 추가`를 누르거나 등록된 파일 영역으로 드래그 앤 드롭하여 여러 이미지를 등록합니다.
2. 목록에서 기준 이미지를 선택하고 미리보기에서 마우스로 Static ROI를 드래그합니다. 같은 좌표의 ROI가 등록된 모든 이미지에 적용됩니다.
3. `인식 언어`에서 언어명 또는 코드로 검색해 주 언어를 선택합니다. 영어가 아닌 언어에는 영어가 자동으로 함께 적용됩니다. 필요한 모델이 없다면 톱니바퀴 설정에서 `모델 자동 다운로드`를 체크합니다.
4. 톱니바퀴 아이콘에 마우스를 올리거나 클릭하면 설정 팝업이 열립니다. `선택 이미지 배율`에서 `1x`, `2x`, `4x` 중 확대 배율을 지정합니다. 전처리 확대 배율은 최대 4배로 제한됩니다. 여러 행을 선택하면 배율이 함께 적용됩니다.
5. 같은 팝업에서 터미널이나 콘솔 화면은 `콘솔 전처리 ON`을 선택해 색 번짐을 제거할 수 있습니다. 이 모드에는 `1x` 배율을 권장합니다. 팝업 밖으로 마우스를 옮기거나 바깥을 클릭하거나 `Esc`를 누르면 설정 팝업이 닫힙니다.
6. `OCR 실행`을 누릅니다.
7. `result/ocr_result_날짜_시간.csv`에서 추출 문자열과 EasyOCR 평균 신뢰도를 확인합니다.

Static ROI는 `OCR 실행` 시 등록된 모든 이미지에 일괄 적용됩니다. 이미지 크기가 ROI보다 작으면 이미지 경계 안의 영역만 처리합니다. 오른쪽 클릭 또는 `Static ROI 해제` 버튼으로 ROI를 제거할 수 있으며, ROI가 없으면 모든 이미지의 전체 영역을 처리합니다.

미리보기에서 마우스 휠로 커서 위치를 중심으로 확대·축소할 수 있습니다. 확대 후에는 스크롤바로 이동하고, 왼쪽 더블클릭으로 전체 이미지에 맞춥니다. ROI는 원본 이미지의 픽셀 좌표로 유지되며, 확대·축소한 화면에서 새로 지정해도 원본 좌표로 저장됩니다. 미리보기 확대·축소는 OCR 처리용 `선택 배율`에 영향을 주지 않습니다.

한국어를 포함한 언어 모델은 `모델 자동 다운로드`를 체크한 상태에서 OCR을 실행할 때 다운로드됩니다.

## 배포 빌드

`build.ps1`은 제3자 라이선스 수집과 PyInstaller `onedir` 빌드를 순서대로 실행합니다. OCR 모델 파일은 빌드에 포함하지 않습니다.

```powershell
.\build.ps1
```

완성된 진입점은 `dist/OCRTool/OCRTool.exe`입니다. GitHub Release에 올릴 ZIP과
SHA-256 파일은 `dist/OCRTool-0.1.0-windows-x64.zip` 및 `.sha256`으로 생성됩니다.
버전을 변경하려면 `build.ps1 -Version 0.2.0`처럼 실행합니다. `models` 폴더는 첫 OCR
실행 시 자동으로 생성됩니다.

배포본의 OCR 파이프라인을 화면 없이 점검하려면 다음 진단 명령을 사용할 수 있습니다. 성공하면 배포 폴더의 `result/`에 CSV가 생성됩니다.

```powershell
.\dist\OCRTool\OCRTool.exe --smoke-ocr ".\sample.png"
```

## GitHub 공개와 Release

저장소에는 소스 코드만 커밋합니다. `.gitignore`에 `dist/`, `build/`, 가상환경,
OCR 모델 및 결과 파일이 포함되어 있습니다.

버전 태그를 올리면 GitHub Actions가 테스트와 Windows 빌드를 실행하고 ZIP과
SHA-256 파일이 첨부된 GitHub Release를 자동으로 생성합니다.

```powershell
git tag v0.1.0
git push origin v0.1.0
```

태그의 `v` 뒤 값은 `build.ps1`에 전달되는 배포 버전입니다. 같은 태그는 다시 사용할
수 없으므로 다음 배포에서는 `v0.1.1`, `v0.2.0`처럼 올립니다.

## 구조

```text
src/ocr_app/
├─ domain/          순수 데이터 모델과 규칙
├─ application/     OCR 처리 유스케이스와 인터페이스
├─ infrastructure/ OpenCV, EasyOCR, CSV 구현체
└─ presentation/   PySide6 UI와 백그라운드 작업
```

`main.py`는 구현 로직을 포함하지 않고 애플리케이션을 조립하고 시작하는 진입점으로만 사용합니다.

## 라이선스

이 프로젝트의 소스 코드는 Apache License 2.0으로 배포됩니다.

구성요소별 고지는 `THIRD_PARTY_NOTICES.md`, 패키지별 라이선스 원문은
`licenses/`에서 확인할 수 있습니다. OCR 모델 파일은 배포하지 않고 첫 사용 시
자동 다운로드합니다.
