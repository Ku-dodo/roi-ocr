# Distribution licenses

`tools/collect_licenses.py`는 현재 Python 환경에 설치된 패키지의 라이선스·NOTICE 파일을 `generated/` 아래에 수집합니다.

`manual/`에는 자동 수집으로 빠지는 LGPLv3/GPLv3 전문과 Qt 배포 고지 템플릿을
보관합니다. 이 폴더는 수집 도구를 다시 실행해도 유지해야 합니다.

배포 전에 생성된 자료가 실제 빌드 환경의 모든 전이 의존성을 포함하는지 회사의 오픈소스 검토 절차로 확인하십시오.
