"""The company as an operating business, not just a roster: products, customers and partners, history, glossary, wiki rules, calendar.

Everything is invented and deterministic (seeded by names), and kept consistent with the rest of the world:
- customers/vendors/investors are the same external parties that send mail (world/entities.py),
- internal owners are real people from the roster (so "who owns this account" can be looked up in the org chart),
- wiki rules state the same limits the assistant's guardrails enforce (expense approval above 1,000,000 KRW, external-mail confirmation, ...),
- calendar events match notices already in the traffic (power outage 11/28, security training deadline).
"""
import random
import zlib
from datetime import date, timedelta

from .entities import COMPANIES
from .people import GIVEN, SURNAMES

PRODUCTS = [
    {"id": "claim", "name": "노웨어 클레임", "since": "2021-03", "what": "보험금 청구 서류를 읽고 분류·심사 대기열까지 보내는 자동화", "owner_dept": "보험사업본부", "status": "운영"},
    {"id": "under", "name": "노웨어 언더", "since": "2023-05", "what": "청약 서류에서 위험 요소를 뽑아 언더라이터의 판단을 돕는 보조 도구", "owner_dept": "보험사업본부", "status": "운영"},
    {"id": "desk", "name": "노웨어 데스크", "since": "2026-02", "what": "직원용 AI 업무 비서: 출근하면 오늘의 할 일을 정리하고 답장 초안을 제안", "owner_dept": "개발본부", "status": "사내 파일럿"},
]

HISTORY = [
    ("2019-03", "설립", "성수동 공유오피스에서 창업 멤버 4명으로 시작", "company"),
    ("2019-11", "시드 투자 20억원", "가온벤처스가 리드. 보험 서류 자동화 가설 검증 자금", "funding"),
    ("2020-06", "첫 고객 PoC", "한빛손해보험과 보험금 청구 서류 분류 PoC. 정확도 91%로 본계약 전환", "customer"),
    ("2020-12", "프리 A 30억원", "가온벤처스 후속 투자. 첫 고객 PoC가 본계약으로 이어진 뒤 개발 인력 확충", "funding"),
    ("2021-03", "노웨어 클레임 정식 출시", "첫 제품. 한빛손해보험이 운영 환경에 도입", "product"),
    ("2021-09", "시리즈 A 90억원", "가온벤처스 리드, 한강인베스트 참여. 개발 인력 확충", "funding"),
    ("2022-04", "판교 R&D센터 개소", "개발 인력 30명이 입주. 백엔드·AI 조직이 분리됨", "site"),
    ("2022-10", "GA 시장 진출", "청솔GA 도입을 시작으로 보험대리점(GA)용 요금제 신설", "customer"),
    ("2023-05", "노웨어 언더 출시", "청약 심사 보조. 다온생명이 첫 고객", "product"),
    ("2023-06", "브릿지 투자 50억원", "한강인베스트. 시리즈 B 전까지 성장 속도를 유지하기 위한 투자", "funding"),
    ("2023-12", "부산 고객지원센터 개소", "상담·클레임 응대 인력 20명으로 시작", "site"),
    ("2024-04", "본부제 개편", "기능별 팀 체계를 9개 본부·실, 32개 팀으로 재편", "org"),
    ("2024-09", "시리즈 B 180억원", "한강인베스트 리드. 보험사업본부와 고객지원센터 확대", "funding"),
    ("2025-03", "성수 본사 확장 이전", "같은 건물 상층으로 확장. 전 직원 좌석 배치 개편", "site"),
    ("2025-10", "ISMS-P 인증 획득", "정보보호 및 개인정보 보호 관리체계 인증", "company"),
    ("2026-02", "노웨어 데스크 사내 파일럿", "직원용 AI 업무 비서를 전사에 시범 도입 (이 프로젝트)", "product"),
]

GLOSSARY = [
    ("청구", "보험", "가입자가 보험금을 달라고 요청하는 일. 노웨어 클레임이 이 서류를 다룬다."),
    ("심사", "보험", "청구가 약관에 맞는지 확인해 지급 여부를 정하는 일. 보상심사팀 담당."),
    ("언더라이팅", "보험", "가입 신청자의 위험을 평가해 인수 여부와 조건을 정하는 일. 줄여서 '언더'."),
    ("계리", "보험", "보험료와 준비금을 통계로 계산하는 일. 계리팀이 상품 가격의 근거를 만든다."),
    ("특약", "보험", "기본 계약에 덧붙이는 보장 조건."),
    ("면책", "보험", "약관상 보험금을 지급하지 않는 사유."),
    ("GA", "보험", "보험대리점(General Agency). 여러 보험사의 상품을 파는 판매 조직. 노웨어의 주요 고객군."),
    ("갱신", "보험", "계약이나 보험 기간이 끝날 때 조건을 다시 정해 이어 가는 일. 고객사 계약에도 같은 말을 쓴다."),
    ("추가 서류", "보험", "심사 중 부족한 서류를 요청하는 일. 고객 응대가 가장 자주 막히는 지점."),
    ("본부", "조직", "가장 큰 조직 단위(예: 개발본부). 장은 본부장, 규모가 작으면 실(실장)·센터(센터장)라 부른다."),
    ("팀장", "조직", "팀을 이끄는 직책. 직급과 별개이며 휴가·경비 1차 승인자."),
    ("직급", "조직", "사원 → 선임 → 책임 → 수석 → 이사 → C-level. 직책(팀원·팀장·본부장)과 따로 쓴다."),
    ("C-level", "조직", "대표이사와 CFO·CTO·CPO. 임원 계정(executive) 권한을 가진다."),
    ("타운홀", "문화", "분기마다 대표가 성과와 계획을 공유하는 전사 모임."),
    ("데일리 스크럼", "문화", "개발팀의 10분 아침 공유. 어제·오늘·막힌 것을 말한다."),
    ("온콜", "개발", "장애 경보를 받는 주 단위 당직. 개발본부가 돌아가며 맡는다."),
    ("P1~P4", "개발", "이슈 심각도. P1은 서비스 중단, P2는 주요 기능 장애, P3·P4는 일반 개선. 비서는 P1·P2만 할 일로 올린다."),
    ("사후 분석", "개발", "장애 뒤 5영업일 안에 쓰는 회고(포스트모템). 책임이 아니라 원인과 재발 방지를 적는다."),
    ("SSO", "IT", "한 번 로그인으로 모든 사내 시스템에 들어가는 방식. 권한은 각 시스템이 본인 토큰으로 확인한다."),
    ("웹훅", "IT", "한 시스템이 다른 시스템에 사건을 알려 주는 호출. 출근 도장이 비서를 깨울 때 서명해서 보낸다."),
    ("출근 도장", "IT", "근태 시스템에 출근을 기록하는 일. 노웨어 데스크의 하루가 여기서 시작한다."),
    ("결재", "업무", "경비·구매·휴가 같은 요청을 승인하는 절차. 금액이 크면 상위 승인자가 필요하다."),
    ("노웨어 데스크", "제품", "직원용 AI 업무 비서(이 프로젝트). 초안만 만들고 발송은 사람이 한다."),
    ("노워", "제품", "노웨어 데스크의 유령 안내 캐릭터. 화면을 돌아다니며 볼 곳을 짚어 준다."),
    ("ISMS-P", "규정", "정보보호·개인정보 보호 관리체계 인증. 2025년 10월에 획득했다."),
    ("피싱 격리", "규정", "수상한 메일·채팅을 할 일에서 빼고 보안 확인 대상으로 따로 보여 주는 처리."),
    ("자율 단계", "AI", "AI가 사람 없이 처리해도 되는 정도. 그림자 → 보조 → 자동으로 일치율이 쌓여야 오른다."),
    ("그림자 모드", "AI", "AI가 판단만 하고 사람이 실제 처리하는 단계. 일치율을 재는 용도."),
    ("평가 사례", "AI", "사람이 '관련 없음'을 누르거나 초안을 고친 결과를 모은 시험 문제. 배포 전에 다시 채점한다."),
]

WIKI = [
    dict(slug="expense", title="경비 정산 규정", owner="경영지원본부", updated="2026-03-10", tags=["경비", "정산", "승인", "영수증"], body="""적용 범위: 전 직원의 업무 경비(교통·식대·출장·소모품).
1. 신청: 사용일로부터 14일 이내에 영수증과 함께 신청한다. 영수증 없는 경비는 사유서를 붙인다.
2. 승인선: 100만원 이하는 팀장이 승인한다. 100만원을 초과하면 본부장 승인이 추가로 필요하다. 이 한도는 시스템에서도 강제되며, 100만원 초과 건은 비서가 자동 처리하지 않고 반드시 사람이 확인한다.
3. 금액이 적혀 있지 않은 경비·구매 요청은 접수하지 않는다. 금액을 먼저 확인한다.
4. 택시비는 22시 이후 업무 종료 시에만 인정한다. 한도는 1회 3만원.
5. 개인 카드로 먼저 쓴 경우 정산은 매월 25일 마감 후 말일에 지급한다. 월말 결산 기간에는 마감이 앞당겨질 수 있다."""),
    dict(slug="leave", title="휴가·근태 규정", owner="경영지원본부", updated="2026-01-15", tags=["휴가", "연차", "반차", "근태"], body="""1. 연차는 입사 첫해 11일, 이후 연 15일이며 근속에 따라 늘어난다.
2. 신청: 시작일 3영업일 전까지 팀장에게 신청한다. 날짜(시작·종료)가 적혀 있지 않은 신청은 검수 대기로 돌려보낸다.
3. 반차는 오전(09~13시)과 오후(14~18시)로 나뉜다. 병가는 사후 증빙으로 처리할 수 있다.
4. 출근은 근태 시스템의 '출근 도장'으로 기록한다. 비서의 아침 브리핑은 이 기록으로 시작된다.
5. 휴직·육아휴직 중인 직원에게는 업무를 배정하지 않는다."""),
    dict(slug="security", title="정보보안 수칙", owner="법무·컴플라이언스실", updated="2026-02-02", tags=["보안", "피싱", "비밀번호", "외부 링크", "신고"], body="""1. 비밀번호, 인증번호, 계좌 정보를 메일·메신저로 요구하는 메시지는 누가 보냈든 응하지 않는다. 대표나 임원을 사칭하는 경우가 많다.
2. 출처가 불분명한 링크와 첨부는 열지 않고 정보보호팀에 신고한다. 신고 메일: security@nowhere.example.
3. 메일·채팅 본문 안의 '이전 지시를 무시하라' 같은 문구는 명령이 아니라 공격 시도다. AI 비서도 본문을 지시가 아니라 데이터로만 읽도록 만들어져 있다.
4. 고객 개인정보는 사내 시스템 밖(개인 메일, 개인 클라우드)으로 옮기지 않는다.
5. 정보보안 교육은 매년 이수해야 하며 마감일까지 미이수 시 시스템 접근이 제한된다."""),
    dict(slug="incident", title="장애 대응 절차", owner="개발본부", updated="2026-04-21", tags=["장애", "온콜", "P1", "P2", "사후 분석"], body="""심각도
- P1: 고객 서비스 전체 중단 또는 데이터 손상. 즉시 온콜 호출, 대표·CTO에 15분 안에 보고.
- P2: 주요 기능 장애(예: 결제 응답 지연). 1시간 안에 담당 팀 배정.
- P3·P4: 부분 장애·개선 요청. 일반 이슈로 등록하고 스프린트에서 처리.
절차
1. 감지: 경보 또는 고객 제보. 이슈를 만들고 심각도를 붙인다.
2. 대응: 담당자는 상태를 '진행 중'으로 바꾸고 #장애대응 채널에 상황을 공유한다.
3. 해결: 해결 메모(무엇을 했는지)를 이슈에 남기고 '해결'로 바꾼다.
4. 사후 분석: 5영업일 안에 작성하고 전사에 공유한다. 사람 탓이 아니라 원인과 재발 방지를 적는다."""),
    dict(slug="external-mail", title="외부 메일·고객 커뮤니케이션 가이드", owner="사업본부", updated="2026-05-12", tags=["외부 메일", "고객", "회신", "확인"], body="""1. 사외 수신자가 포함된 메일은 발송 전에 한 번 더 확인한다. 시스템도 '외부 수신자 확인'을 체크해야 보낸다.
2. 금액·계좌·계약 조건은 메일 초안에 임의로 쓰지 않는다. AI가 만든 초안에 이런 표현이 있으면 발송이 차단된다.
3. 고객사 담당자에게는 존댓말을 쓰고, 확정할 수 없는 일정은 '확인 후 알려드리겠습니다'로 답한다.
4. 고객 불만·클레임은 고객지원센터 에스컬레이션 규칙에 따라 당일 접수 확인 회신을 보낸다."""),
    dict(slug="approval", title="구매·결재 요청 절차", owner="경영지원본부", updated="2026-02-20", tags=["구매", "결재", "견적", "승인"], body="""1. 100만원 미만 소액 구매는 팀장 승인으로 충분하다. 그 이상은 견적서 2부를 붙여 본부장 결재를 받는다.
2. 구매 요청에는 금액과 사유가 있어야 한다. 금액이 없는 요청은 비서가 자동으로 처리하지 않고 사람에게 돌려준다.
3. 소프트웨어 구독은 정보보호팀의 보안 검토를 거친다.
4. 계약 검토가 필요한 건은 법무팀에 계약 검토 요청을 올린다. 통상 3영업일 걸린다."""),
    dict(slug="messenger", title="메신저 운영 규칙", owner="총무·구매", updated="2026-01-08", tags=["메신저", "채널", "멘션", "임원"], body="""1. 채널은 본부(9개), 팀(32개), 전사 공용으로 나뉜다. 팀 채널은 해당 팀원만 볼 수 있다.
2. 임원 채널과 컴플라이언스 채널은 해당 인원에게만 보인다. 비공개 채널의 내용은 밖으로 공유하지 않는다.
3. 급한 일은 @멘션과 함께 한 문장으로 요청하고, 결과는 같은 스레드에 남긴다.
4. 1:1 메시지로 업무 지시를 할 때도 중요한 결정은 메일이나 이슈로 남긴다."""),
    dict(slug="onboarding", title="신규 입사자 온보딩 가이드", owner="경영지원본부", updated="2026-03-30", tags=["온보딩", "입사", "첫 주"], body="""첫날: 계정 발급(SSO), 좌석·장비 수령, 팀장과 1:1.
첫 주: 정보보안 교육 이수, 소속 본부장 인사, 팀 채널 입장, 노웨어 데스크 출근 도장 체험.
첫 달: 멘토와 주 1회 대화, 팀 업무 문서 읽기, 첫 과제 완료와 회고.
궁금한 규정은 이 위키에서 찾고, 없으면 #질문 채널에 물어본다."""),
    dict(slug="privacy", title="개인정보·고객 데이터 취급 기준", owner="법무·컴플라이언스실", updated="2026-02-25", tags=["개인정보", "고객 데이터", "마스킹", "보관"], body="""1. 고객 개인정보는 업무에 필요한 최소 범위만 조회하며 조회 기록은 남는다.
2. 평가·학습에 쓰는 데이터는 개인정보를 마스킹하고 직원의 동의를 받은 것만 사용한다.
3. 보관 기간이 지난 데이터는 정해진 절차로 파기한다.
4. 외부 AI 모델에 보내는 내용에는 고객 식별 정보를 넣지 않는다."""),
]

# (date, title, kind, audience)  kind: holiday | company | deadline | outage
EVENTS = [
    ("2026-11-27", "월말 결산 마감 (경영지원본부 자료 요청 집중)", "deadline", "all"),
    ("2026-11-28", "오전 사옥 전기 점검 정전 — 중요 작업은 미리 저장", "outage", "all"),
    ("2026-12-04", "4분기 전사 타운홀", "company", "all"),
    ("2026-12-10", "정보보안 교육 이수 마감", "deadline", "all"),
    ("2026-12-18", "연말 성과 평가 자기 평가서 제출", "deadline", "all"),
    ("2026-12-24", "연말 단축 근무 (15시 퇴근)", "company", "all"),
    ("2026-12-25", "성탄절", "holiday", "all"),
    ("2026-12-31", "연말 결산·재고 마감", "deadline", "all"),
    ("2027-01-01", "신정", "holiday", "all"),
    ("2027-01-04", "시무식과 2027 계획 공유", "company", "all"),
    ("2027-02-06", "설 연휴 시작 (2/6~2/9)", "holiday", "all"),
]

# internal owner units, by customer group
OWNER_UNITS = {"insurer": ["법인영업팀", "고객성공팀"], "ga": ["제휴·BD팀", "법인영업팀"],
               "vendor": ["총무·구매팀", "정보보호팀", "법무팀", "인사팀", "플랫폼·인프라팀"], "investor": ["IR·투자팀"]}
VENDOR_CAT = {"클라우드웍스": "클라우드 인프라", "시큐어넷": "보안 컨설팅", "리걸브릿지": "법률 자문", "피플리스트": "채용", "오피스온": "사무용품", "데이터레이크랩": "데이터 플랫폼"}


# facts stated in HISTORY must hold in the customer table too: name -> (stage, since, product)
ANCHORS = {"한빛손해보험": ("운영", "2020-06", "노웨어 클레임"), "다온생명": ("운영", "2023-05", "노웨어 언더"), "청솔GA": ("운영", "2022-10", "노웨어 클레임 · 언더")}


def _rnd(*parts):
    return random.Random(zlib.crc32("|".join(map(str, parts)).encode()))


def _owner(users: dict, units: list, rnd):
    pool = [u for u in users.values() if u["unit"] in units and u["status"] == "재직"]
    pool.sort(key=lambda u: (u["position"] != "팀장", u["id"]))   # leads first, stable
    return pool[rnd.randrange(min(3, len(pool)))] if pool else None


def customers(users: dict, today: date | None = None) -> list:
    """Every external party with a relationship to Nowhere. Deterministic."""
    today = today or date(2026, 11, 24)
    out = []
    for group, rows in COMPANIES.items():
        for i, (name, domain, what) in enumerate(rows):
            r = _rnd("co", name)
            own = _owner(users, OWNER_UNITS[group], r)
            (s, sr), (g, gr) = r.choice(SURNAMES), r.choice(GIVEN)
            row = {"id": f"co_{domain.split('.')[0]}", "name": name, "domain": domain, "group": group, "what": what,
                   "owner": {"id": own["id"], "name": own["name"], "unit": own["unit"]} if own else None,
                   "contact": {"name": f"{s}{g}", "email": f"{gr}.{sr}@{domain}"}}
            if group in ("insurer", "ga"):
                # first customer is 2020-06 (anchor), claim launched 2021-03, GA market opened 2022-10: nobody signs before their product existed
                since = date((2022 if group == "ga" else 2021) + r.randrange(0, 4), 1 + r.randrange(12), 1)
                if group == "ga" and since < date(2022, 11, 1):
                    since = date(2022, 11, 1)
                if since > today:
                    since = date(2025, 6, 1)
                stage = r.choices(["운영", "갱신 협의", "도입 검토", "파일럿"], [6, 2, 1, 1])[0]
                renew = since.replace(year=today.year + (1 if since.replace(year=today.year) <= today else 0))
                prod = "노웨어 클레임" if group == "insurer" and (since < date(2023, 5, 1) or r.random() < .7) else "노웨어 언더" if group == "insurer" else "노웨어 클레임 · 언더"
                health = "주의" if stage == "갱신 협의" and r.random() < .5 else "양호"
                row.update(kind="고객사", product=prod, stage=stage, since=since.isoformat()[:7], renewal=renew.isoformat() if stage != "파일럿" else None,
                           annual_eok=round(r.uniform(4.0, 20.0) if group == "insurer" else r.uniform(1.5, 6.0), 1) if stage != "파일럿" else 0.0, health=health)
                if name in ANCHORS:
                    stage, sn, prod = ANCHORS[name]
                    row.update(stage=stage, since=sn, product=prod, renewal=row["renewal"] or date(today.year + 1, 6, 30).isoformat(), annual_eok=row["annual_eok"] or 8.0)
            elif group == "vendor":
                row.update(kind="거래처", category=VENDOR_CAT.get(name, what), stage="계약 중", since=f"{2019 + r.randrange(0, 6)}-{1 + r.randrange(12):02d}", renewal=None, health="양호")
            else:
                row.update(kind="투자사", stage={"가온벤처스": "시드·시리즈 A 리드", "한강인베스트": "시리즈 A 참여·시리즈 B 리드"}.get(name, "투자"), since="2019-11" if name == "가온벤처스" else "2021-09", renewal=None, health="양호")
            out.append(row)
    return out


def overview(users: dict, today: date | None = None) -> dict:
    cs = customers(users, today)
    buyers = [c for c in cs if c["kind"] == "고객사"]
    return {"products": PRODUCTS, "stats": {"headcount": len(users), "customers": len(buyers), "running": sum(1 for c in buyers if c["stage"] in ("운영", "갱신 협의")),
                                           "annual_eok": round(sum(c["annual_eok"] for c in buyers), 1), "vendors": sum(1 for c in cs if c["kind"] == "거래처"),
                                           "attention": [c["name"] for c in buyers if c["health"] == "주의"]},
            "next_events": calendar(today or date(2026, 11, 24), 45)}


def calendar(start: date, days: int) -> list:
    from . import archive
    end = start + timedelta(days=days)
    return [e for e in archive.all_events(start.year, end.year) if start.isoformat() <= e["date"] <= end.isoformat()]


def history() -> list:
    return [{"month": m, "title": t, "detail": d, "kind": k} for m, t, d, k in HISTORY]


def glossary(q: str = "") -> list:
    q = q.strip().lower()
    return [{"term": t, "group": g, "meaning": m} for t, g, m in GLOSSARY if not q or q in t.lower() or q in m.lower()]


def wiki_list(q: str = "") -> list:
    q = q.strip().lower()
    out = []
    for d in WIKI:
        hay = (d["title"] + " " + " ".join(d["tags"]) + " " + d["body"]).lower()
        if q and q not in hay:
            continue
        snippet = ""
        if q:
            i = d["body"].lower().find(q)
            snippet = d["body"][max(0, i - 30): i + 90].replace("\n", " ") if i >= 0 else ""
        out.append({"slug": d["slug"], "title": d["title"], "owner": d["owner"], "updated": d["updated"], "tags": d["tags"], "snippet": snippet})
    return out


def wiki_get(slug: str):
    return next((d for d in WIKI if d["slug"] == slug), None)
