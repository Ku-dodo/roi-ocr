from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OcrLanguage:
    code: str
    name: str
    model_filename: str

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.code})"


def _languages(
    model_filename: str, entries: tuple[tuple[str, str], ...]
) -> tuple[OcrLanguage, ...]:
    return tuple(OcrLanguage(code, name, model_filename) for code, name in entries)


# EasyOCR 1.7.2의 all_lang_list와 인식 모델 선택 규칙을 애플리케이션의
# 순수 도메인 데이터로 옮긴 목록이다. UI와 배포 도구가 같은 정보를 사용한다.
SUPPORTED_LANGUAGES: tuple[OcrLanguage, ...] = (
    *_languages(
        "latin_g2.pth",
        (
            ("af", "아프리칸스어"),
            ("az", "아제르바이잔어"),
            ("bs", "보스니아어"),
            ("cs", "체코어"),
            ("cy", "웨일스어"),
            ("da", "덴마크어"),
            ("de", "독일어"),
            ("es", "스페인어"),
            ("et", "에스토니아어"),
            ("fr", "프랑스어"),
            ("ga", "아일랜드어"),
            ("hr", "크로아티아어"),
            ("hu", "헝가리어"),
            ("id", "인도네시아어"),
            ("is", "아이슬란드어"),
            ("it", "이탈리아어"),
            ("ku", "쿠르드어"),
            ("la", "라틴어"),
            ("lt", "리투아니아어"),
            ("lv", "라트비아어"),
            ("mi", "마오리어"),
            ("ms", "말레이어"),
            ("mt", "몰타어"),
            ("nl", "네덜란드어"),
            ("no", "노르웨이어"),
            ("oc", "오크어"),
            ("pi", "팔리어"),
            ("pl", "폴란드어"),
            ("pt", "포르투갈어"),
            ("ro", "루마니아어"),
            ("rs_latin", "세르비아어(라틴 문자)"),
            ("sk", "슬로바키아어"),
            ("sl", "슬로베니아어"),
            ("sq", "알바니아어"),
            ("sv", "스웨덴어"),
            ("sw", "스와힐리어"),
            ("tl", "타갈로그어"),
            ("tr", "튀르키예어"),
            ("uz", "우즈베크어"),
            ("vi", "베트남어"),
        ),
    ),
    OcrLanguage("en", "영어", "english_g2.pth"),
    *_languages(
        "arabic.pth",
        (("ar", "아랍어"), ("fa", "페르시아어"), ("ug", "위구르어"), ("ur", "우르두어")),
    ),
    *_languages(
        "bengali.pth",
        (("bn", "벵골어"), ("as", "아삼어"), ("mni", "마니푸르어")),
    ),
    *_languages(
        "cyrillic_g2.pth",
        (
            ("ru", "러시아어"),
            ("rs_cyrillic", "세르비아어(키릴 문자)"),
            ("be", "벨라루스어"),
            ("bg", "불가리아어"),
            ("uk", "우크라이나어"),
            ("mn", "몽골어"),
            ("abq", "아바자어"),
            ("ady", "아디게어"),
            ("kbd", "카바르다어"),
            ("ava", "아바르어"),
            ("dar", "다르기어"),
            ("inh", "인구시어"),
            ("che", "체첸어"),
            ("lbe", "라크어"),
            ("lez", "레즈긴어"),
            ("tab", "타바사란어"),
            ("tjk", "타지크어"),
        ),
    ),
    *_languages(
        "devanagari.pth",
        (
            ("hi", "힌디어"),
            ("mr", "마라티어"),
            ("ne", "네팔어"),
            ("bh", "비하르어"),
            ("mai", "마이틸리어"),
            ("ang", "앙기카어"),
            ("bho", "보즈푸리어"),
            ("mah", "마가히어"),
            ("sck", "나그푸리어"),
            ("new", "네와르어"),
            ("gom", "콘칸어"),
            ("sa", "산스크리트어"),
            ("bgc", "하리안비어"),
        ),
    ),
    OcrLanguage("th", "태국어", "thai.pth"),
    OcrLanguage("ch_sim", "중국어(간체)", "zh_sim_g2.pth"),
    OcrLanguage("ch_tra", "중국어(번체)", "chinese.pth"),
    OcrLanguage("ja", "일본어", "japanese_g2.pth"),
    OcrLanguage("ko", "한국어", "korean_g2.pth"),
    OcrLanguage("ta", "타밀어", "tamil.pth"),
    OcrLanguage("te", "텔루구어", "telugu.pth"),
    OcrLanguage("kn", "칸나다어", "kannada.pth"),
)

LANGUAGE_BY_CODE = {language.code: language for language in SUPPORTED_LANGUAGES}


def get_language(code: str) -> OcrLanguage:
    try:
        return LANGUAGE_BY_CODE[code]
    except KeyError as error:
        raise ValueError(f"지원하지 않는 OCR 언어입니다: {code}") from error


def reader_languages(primary_code: str) -> tuple[str, ...]:
    """Return an EasyOCR-compatible language list for one primary language."""
    get_language(primary_code)
    return ("en",) if primary_code == "en" else (primary_code, "en")


def is_language_model_installed(primary_code: str, model_directory: Path) -> bool:
    language = get_language(primary_code)
    return (model_directory / language.model_filename).is_file()
