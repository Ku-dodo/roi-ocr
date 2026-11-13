import csv, json, hashlib
from pathlib import Path

base = Path('C:/Users/kudh/Pictures/LangTestPack')
out = Path(__file__).resolve().parent.parent
with (base/'Test용.csv').open(encoding='utf-8-sig', newline='') as f:
    template = list(csv.reader(f))[1:]
with (base/'ocr_result_20261112_220648_446284.csv').open(encoding='utf-8-sig', newline='') as f:
    raw = list(csv.reader(f))
ids = [r[0] for r in template[:14]]
texts = {
 'en': ['Campaign', 'Mission', 'Area 22 22nd Mission', 'Story', 'Tales of Youth and School Days', 'Bounty', 'Commissions', 'Scrimmage', 'Tactical Challenge', 'Clear: 13', 'Final Restriction Release', 'Total Assault', 'Joint Firing Drill', 'Grand Assault'],
 'ko': ['업무', '임무', 'Area 22 제 22임무', '스토리', '학원과 청춘의 이야기', '현상수배', '특별의뢰', '학원교류회', '전술 대회', 'Clear: 13', '제약해제결전', '총력전', '종합전술시험', '대결전'],
 'th': ['งาน', 'ภารกิจ', 'พื้นที่ 22 ภารกิจบทที่ 22', 'เนื้อเรื่อง', 'เรื่องราวที่สดใสกับชีวิตในโรงเรียน', 'ประกาศจับ', 'คำขอพิเศษ', 'ทัวร์โรงเรียน', 'อารีน่า', 'Clear: 13', 'ศึกทลายพันธะ', 'เรดบอส', 'สอบประมวล', 'แกรนด์เรดบอส'],
 'ch_tra': ['任務', '任務', 'Area 22 第22任務', '劇情', '學園與青春的故事', '懸賞通緝', '特殊任務', '學園交流會', '戰術大賽', 'Clear: 13', '制約解除決戰', '總力戰', '綜合戰術考試', '大決戰'],
}
coords = {'Scene_Title':(145,9,400,59), 'Mission_Title':(1040,340,1270,382), 'Mission_Data':(1035,378,1290,418), 'Story_Title':(1600,340,1790,382), 'Story_Description':(1600,383,1860,420), 'Bounty_Title':(1005,592,1175,637), 'Commissions_Title':(980,746,1165,790), 'Scrimmage_Title':(955,900,1120,943), 'Tactical_Title':(1220,899,1400,940), 'Final_Data':(1420,864,1520,897), 'Final_Title':(1420,899,1590,947), 'Total_Title':(1260,663,1445,709), 'Joint_Title':(1460,663,1645,709), 'Grand_Title':(1658,663,1835,709)}
files = {l:'Campaign_'+('zh_cn' if l=='ch_tra' else l)+'.png' for l in texts}
ocr = {(r[0],r[1]):r for r in raw[1:]}
db, audit = [], []
for ident, lang, *_ in template:
    final = texts[lang][ids.index(ident)]
    old = ocr[(ident,lang)]
    notes = []
    if ident == 'Mission_Data':
        notes.append('문자 사이 공백은 화면의 시각적 간격을 전사; 원본 리소스의 공백 코드포인트는 확인 불가')
    if ident == 'Final_Title' and lang == 'en':
        notes.append('화면 자동 줄바꿈은 한 칸 공백으로 연결; 리소스의 명시적 개행 여부는 확인 불가')
    if lang == 'ch_tra':
        notes.append('파일명 zh_cn과 달리 화면은 번체; 템플릿 ch_tra 유지')
    if old[2] != final:
        if ident in ('Mission_Data','Tactical_Title') and lang != 'th':
            notes.append('이미지 기준 띄어쓰기 전사')
        elif ident=='Final_Data':
            notes.append('Clear의 대문자 C 확인')
        else:
            notes.append('확대 이미지 기준 OCR 오인식 수정')
    status = '이미지 대조 완료'
    db.append([ident,lang,final])
    audit.append(old + [final, '수정' if old[2]!=final else '유지', status, files[lang], ', '.join(map(str,coords[ident])), '; '.join(notes)])

assert len(db)==len(audit)==56
assert len({tuple(r[:2]) for r in db})==56
assert set(ocr)=={tuple(r[:2]) for r in db}
sources=[]
for name in ['Test용.csv','ocr_result_20261112_220648_446284.csv',*files.values()]:
    p=base/name
    sources.append([name,str(p),hashlib.sha256(p.read_bytes()).hexdigest()])
rules=[
 ['범위','Test용.csv의 UI ID 14개 × 언어 4개 = 56행. 원본의 키·행 순서 유지.'],
 ['DB 열','UI ID + 언어가 복합키이며 문자열이 이미지 대조 후 최종 전사값. CSV도 같은 3열이다.'],
 ['언어 코드','en=영어, ko=한국어, th=태국어, ch_tra=중국어 번체. 기존 시스템 호환을 위해 템플릿 코드 유지.'],
 ['중국어 파일명','Campaign_zh_cn.png는 파일명과 달리 번체 화면이다. zh_cn 또는 간체 데이터로 사용하지 않는다.'],
 ['검수 방법','제공된 네 이미지의 UI 위치를 대조하고, 작은 문구를 확대하여 OCR 결과를 수정했다. 번역을 새로 만들지 않았다.'],
 ['검수 상태','이미지 대조 완료는 화면 전사 검수이다. 게임 리소스·공식 문자열 테이블과의 코드포인트 일치 인증은 아니다.'],
 ['공백의 한계','이미지만으로 U+0020/U+00A0, 혼합 글꼴 간격, 명시적 공백 유무를 확정할 수 없다. Mission_Data는 시각적 단어 간격을 공백으로 전사했다.'],
 ['줄바꿈','영문 Final_Title의 화면 2줄은 한 칸 공백으로 연결했다. 다른 항목은 화면의 한 줄 문구를 전사했다. 리소스의 명시적 개행은 확인 불가하다.'],
 ['수치','Area 22, 임무 22, Clear: 13은 제공 화면의 관측값이다. 숫자 치환·자리표시자화를 하지 않았다.'],
 ['OCR 신뢰도','검수이력의 상태·신뢰도는 OCR CSV 원본값이다. 수정 후 정확도나 사람 검수 신뢰도로 재해석하지 않는다.'],
 ['추적 방법','검수이력의 첫 5열은 제공 OCR CSV와 동일하다. 최종 문자열·변경 여부·검수·이미지·좌표·비고를 뒤에 추가했다.'],
 ['좌표 규칙','이미지 좌상단 원점의 픽셀 좌표 (left, top, right, bottom). 전체 이미지 1919 × 1079 기준의 확인 영역이다.'],
 ['제외 범위','템플릿에 없는 이벤트 배지, 남은 일수, 캐릭터 대사, 재화 수치, 잠금 메뉴, 배경 글자는 DB에 추가하지 않았다.'],
 ['원본 보존','원본 이미지와 CSV는 변경하지 않았다. 아래 SHA-256은 입력 파일의 식별용 해시이다.'],
]
payload={'db':[['UI ID','언어','문자열']]+db,'audit':[raw[0]+['최종 문자열','변경 여부','검수','출처 이미지','확인 영역 (L,T,R,B)','비고']]+audit,'rules':[['항목','작성 기준 / 제한']]+rules, 'sources':[['원본 파일','원본 경로','SHA-256']]+sources}
(out/'work/data.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
with (out/'L10N_DB.csv').open('w',encoding='utf-8-sig',newline='') as f:
    csv.writer(f).writerows(payload['db'])
print(json.dumps({'rows':len(db),'changes':sum(a[6]=='수정' for a in audit),'changed':[[a[0],a[1],a[2],a[5]] for a in audit if a[6]=='수정']},ensure_ascii=False,indent=2))
