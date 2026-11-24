"""Seven years of company records, 2019-2026: quarterly numbers, history, incidents, town halls, holidays and recurring events.

A company founded in March 2019 has something for every year since, and the numbers must agree with each other:
- headcount at a date = people on the roster hired by then, scaled up for people who have since left (one fixed attrition rate, so it is
  reproducible); today's value is exactly the roster size,
- customers come from the customer table (contracts start when they start; nobody signs before the product exists),
- revenue = contract value * a ramp (contracts grew over time) / 4 per quarter,
- executives "joined" in the history on the dates the roster says they were hired,
- holidays are the real public holidays; recurring company events are computed per year (never on a weekend).
Nothing here is random at request time: same roster, same answer.
"""
import random
import zlib
from datetime import date, timedelta

NOW = date(2026, 11, 24)           # "today" of the world
FIRST_YEAR = 2019
ATTRITION = 0.96                    # share of a year's people still here a year later (used to estimate who had already left)

# real public holidays (main day only; substitute holidays omitted)
LUNAR = {  # year -> (설날, 부처님오신날, 추석)
    2019: ("2019-02-05", "2019-05-12", "2019-09-13"), 2020: ("2020-01-25", "2020-04-30", "2020-10-01"), 2021: ("2021-02-12", "2021-05-19", "2021-09-21"),
    2022: ("2022-02-01", "2022-05-08", "2022-09-10"), 2023: ("2023-01-22", "2023-05-27", "2023-09-29"), 2024: ("2024-02-10", "2024-05-15", "2024-09-17"),
    2025: ("2025-01-29", "2025-05-05", "2025-10-06"), 2026: ("2026-02-17", "2026-05-24", "2026-09-25"), 2027: ("2027-02-07", "2027-05-13", "2027-09-15"),
}
FIXED = [("01-01", "신정"), ("03-01", "삼일절"), ("05-05", "어린이날"), ("06-06", "현충일"), ("08-15", "광복절"), ("10-03", "개천절"), ("10-09", "한글날"), ("12-25", "성탄절")]

EXTRA_HISTORY = [
    ("2019-04", "서비스 기획안 확정", "보험금 청구 서류를 읽고 분류하는 제품을 첫 목표로 결정", "company"),
    ("2019-08", "첫 직원 채용", "개발자와 영업 담당이 합류해 창업 멤버 4명이 10명이 됨", "org"),
    ("2020-03", "전사 재택근무 전환", "코로나로 한 달간 전원 재택. 이후 주 2회 출근 체계 유지", "org"),
    ("2020-10", "성수 독립 사무실 입주", "공유오피스를 떠나 첫 독립 사무실 입주", "site"),
    ("2021-06", "코드 리뷰 문화 도입", "모든 변경에 리뷰어 1명 이상. 이후 배포 사고가 줄어듦", "company"),
    ("2021-11", "보험사업본부 신설", "상품개발·언더라이팅 인력이 합류해 클레임·언더 제품을 전담", "org"),
    ("2022-01", "정보보호 담당 첫 채용", "금융권 고객 보안 점검 요구에 대응", "org"),
    ("2022-07", "SaaS 요금제 개편", "사용량 기반에서 좌석+사용량 혼합 요금제로 전환", "product"),
    ("2022-12", "첫 전사 워크샵", "제주에서 1박 2일. 이후 매년 10월로 이동", "company"),
    ("2023-03", "사내 메일·메신저 자체 운영", "외부 협업툴에서 자체 사내 시스템(SSO·메일·메신저·이슈)으로 전환", "company"),
    ("2023-08", "타운홀을 분기 행사로", "월간에서 분기 전사 타운홀로 바꿔 성과·계획을 공유", "company"),
    ("2024-01", "데이터분석팀 신설", "제품 지표와 고객 사용 분석을 전담", "org"),
    ("2024-06", "AI·데이터팀 신설", "문서 이해와 LLM 연구 시작. 노웨어 데스크의 출발점", "org"),
    ("2025-01", "정보보안 교육 의무화", "연 1회 이수, 미이수 시 접근 제한", "company"),
    ("2025-06", "고객 간담회", "대표 주관으로 보험사·GA 고객 9곳과 로드맵 공유", "customer"),
    ("2026-04", "장애 대응 절차 개정", "P1은 15분 안에 대표·CTO 보고, 사후 분석 5영업일", "company"),
]

# (date, severity, title, impact, cause, fix, owner unit)
POSTMORTEMS = [
    ("2020-11-17", "P2", "청구 서류 분류 지연", "한빛손해보험 PoC 서류가 6시간 지연 처리", "OCR 대기열 단일 워커", "워커 증설과 재시도 정책", "백엔드1팀"),
    ("2021-08-03", "P1", "클레임 서비스 3시간 중단", "운영 환경 전체 중단, 고객사 1곳 영향", "배포 중 DB 마이그레이션 잠금", "무중단 마이그레이션 절차와 배포 전 체크리스트", "플랫폼·인프라팀"),
    ("2022-03-22", "P2", "서류 이미지 용량 초과", "대용량 스캔 파일 업로드 실패", "업로드 크기 제한 불일치", "게이트웨이와 서버 제한 통일", "백엔드2팀"),
    ("2022-11-09", "P2", "알림 메일 중복 발송", "고객사 담당자에게 같은 알림 4통", "재시도 시 멱등 키 누락", "멱등 키와 발송 이력 도입", "백엔드1팀"),
    ("2023-06-14", "P1", "언더 서비스 오분류", "청약 서류 일부가 잘못된 위험군으로 분류", "모델 버전과 규칙 버전 불일치", "배포 전 평가 게이트와 기준선 도입", "AI·데이터팀"),
    ("2024-02-27", "P2", "결제 응답 지연", "청구 결과 전송이 평균 9초 지연", "외부 보험사 API 타임아웃 설정", "서킷 브레이커와 큐잉", "플랫폼·인프라팀"),
    ("2024-10-15", "P2", "권한 설정 누락", "일부 직원이 타 팀 이슈를 조회", "이슈 트래커 가시성 규칙 누락", "가시성 규칙 테스트화", "정보보호팀"),
    ("2025-05-08", "P1", "데이터베이스 디스크 부족", "서비스 40분 중단", "로그 증가 경보 임계치 부적절", "경보 개선과 보관 주기 정책", "플랫폼·인프라팀"),
    ("2026-03-19", "P2", "서명 웹훅 검증 실패", "출근 알림이 비서에 도착하지 않음", "서명 키 교체 시 반영 누락", "키 교체 절차에 검증 단계 추가", "백엔드2팀"),
]

TOWNHALL_TOPICS = ["제품 로드맵", "채용과 조직", "고객 성과", "보안과 규정", "비용과 효율", "다음 분기 목표", "문화와 일하는 방식", "투자와 성장 계획"]


def _rnd(*parts):
    return random.Random(zlib.crc32("|".join(map(str, parts)).encode()))


def _weekday_before(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _nth_weekday(y, m, weekday, n):
    d = date(y, m, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))
    return d


def _last_business_day(y, m):
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return _weekday_before(d)


def holidays(year: int) -> list:
    out = [{"date": f"{year}-{md}", "title": t, "kind": "holiday", "audience": "all"} for md, t in FIXED]
    if year in LUNAR:
        for d, t in zip(LUNAR[year], ("설날", "부처님오신날", "추석")):
            out.append({"date": d, "title": t, "kind": "holiday", "audience": "all"})
    return out


def company_events(year: int) -> list:
    ev = []
    if year >= FIRST_YEAR + 1:
        ev.append((_weekday_before(date(year, 1, 2)), "시무식과 올해 계획 공유", "company"))
    if year >= FIRST_YEAR:
        d = date(year, 3, 4)
        if year > FIRST_YEAR:
            ev.append((_weekday_before(d), f"창립 {year - FIRST_YEAR}주년", "company"))
    for m in (3, 6, 9, 12):
        if (year, m) >= (2023, 9):
            ev.append((_nth_weekday(year, m, 4, 1), f"{m // 3}분기 전사 타운홀" if m != 12 else "4분기 전사 타운홀", "company"))
        if year >= 2020:
            ev.append((_last_business_day(year, m), f"{m // 3}분기 결산 마감", "deadline"))
    if year >= 2022:
        ev.append((_nth_weekday(year, 10, 4, 3), "전사 워크샵", "company"))
    if year >= 2025:
        ev.append((_weekday_before(date(year, 12, 10)), "정보보안 교육 이수 마감", "deadline"))
    if year >= 2021:
        ev.append((_weekday_before(date(year, 12, 18)), "연말 성과 평가 자기 평가서 제출", "deadline"))
        ev.append((_weekday_before(date(year, 12, 24)), "연말 단축 근무 (15시 퇴근)", "company"))
    return [{"date": d.isoformat(), "title": t, "kind": k, "audience": "all"} for d, t, k in ev if d.year == year and d >= date(2019, 3, 4)]


def all_events(y0: int, y1: int) -> list:
    from .company import EVENTS   # hand-written, world-specific dates (e.g. the 11/28 power outage notice)
    out, seen = [], set()
    rows = [e for y in range(y0, y1 + 1) for e in holidays(y) + company_events(y)] + [{"date": d, "title": t, "kind": k, "audience": a} for d, t, k, a in EVENTS]
    for e in sorted(rows, key=lambda e: (e["date"], e["title"])):
        key = (e["date"], e["title"][:6])
        if key not in seen and date(2019, 3, 4).isoformat() <= e["date"]:
            seen.add(key)
            out.append(e)
    return out


def _quarter_end(y, q):
    return date(y + (q == 4), (q * 3) % 12 + 1, 1) - timedelta(days=1)


def headcount_at(users: dict, d: date) -> int:
    s = sum(1 for u in users.values() if u["hire_date"] <= d.isoformat())
    if d >= NOW:
        return s
    years = (NOW - d).days / 365.25
    return min(len(users), max(s, round(s / ATTRITION ** years)))


def _buyers(customers: list) -> list:
    return [c for c in customers if c["kind"] == "고객사"]


def _arr_at(buyers: list, d: date) -> float:
    total = 0.0
    for c in buyers:
        if c["stage"] == "파일럿" or c["since"] > d.isoformat()[:7]:
            continue
        ramp = max(0.35, 1 - 0.13 * (NOW - d).days / 365.25)   # contracts were smaller before they grew
        total += (c["annual_eok"] or 0) * ramp
    return round(total, 1)


def longtail_at(d: date) -> int:
    """Small GA/agency subscribers (self-serve plan opened with the GA market in 2022-10): the long tail beside the named accounts."""
    if d < date(2022, 11, 1):
        return 0
    m = (d.year - 2022) * 12 + d.month - 10          # months since 2022-10
    return round(560 / (1 + 2.718281828 ** (-(m - 20) / 7.5)))


def quarters(users: dict, customers: list) -> list:
    """2019Q1 (partial) .. the quarter containing NOW (in progress)."""
    buyers = _buyers(customers)
    out = []
    for y in range(FIRST_YEAR, NOW.year + 1):
        for q in range(1, 5):
            end = _quarter_end(y, q)
            if end < date(2019, 3, 4):
                continue
            if date(y, q * 3 - 2, 1) > NOW:
                break
            at = min(end, NOW)
            ent = _arr_at(buyers, at)
            lt = longtail_at(at)
            tail = round(lt * 0.12 * max(0.5, 1 - 0.05 * (NOW - at).days / 365.25), 1)    # about 0.12 eok per subscriber per year
            arr = round(ent + tail, 1)
            rnd = _rnd("inc", y, q)
            age = (y - FIRST_YEAR) + q / 4
            named = [p for p in POSTMORTEMS if p[0][:4] == str(y) and (int(p[0][5:7]) - 1) // 3 + 1 == q]
            p2 = max(sum(1 for p in named if p[1] == "P2"), rnd.randint(0, 2) + (1 if 1 < age < 5 else 0))
            p1 = max(sum(1 for p in named if p[1] == "P1"), 1 if rnd.random() < max(0.05, .5 - age * .06) else 0)
            custs = sum(1 for c in buyers if c["since"] <= at.isoformat()[:7])
            if not custs and not named:
                p1 = p2 = 0                      # no customers yet: nothing in production to break
            if custs < 2:
                p1 = sum(1 for p in named if p[1] == "P1")   # a P1 needs several customers to hurt
            out.append({"year": y, "quarter": q, "label": f"{y}Q{q}", "end": at.isoformat(), "in_progress": end > NOW,
                        "headcount": headcount_at(users, at), "customers": custs,
                        "arr_eok": arr, "revenue_eok": round(arr / 4, 1), "enterprise_eok": round(ent / 4, 1), "longtail_eok": round(tail / 4, 1), "longtail_customers": lt, "p1": p1, "p2": p2})
    return out


def events_all(users: dict, customers: list) -> list:
    """Company history, newest last: curated milestones + executives joining (roster) + customers signing (customer table)."""
    from .company import HISTORY
    rows = [(m, t, d, k) for m, t, d, k in HISTORY + EXTRA_HISTORY]
    for u in users.values():
        if u["position"] in ("본부장", "실장", "센터장") and u["hire_date"] >= "2019-03-05":
            rows.append((u["hire_date"][:7], f"{u['dept']} {u['position']} 합류", f"{u['name']} {u['title']}", "org"))
    for c in _buyers(customers):
        if c["name"] not in ("한빛손해보험", "다온생명", "청솔GA"):     # those three are already milestones
            rows.append((c["since"], f"{c['name']} 도입", f"{c['product']} · {c['what']}", "customer"))
    return [{"month": m, "title": t, "detail": d, "kind": k} for m, t, d, k in sorted(rows, key=lambda r: (r[0], r[1]))]


def townhalls(qs: list, evs: list) -> list:
    out = []
    for i, q in enumerate(qs):
        if q["year"] < 2020:
            continue
        hi = [e["title"] for e in evs if e["month"][:4] == str(q["year"]) and (int(e["month"][5:7]) - 1) // 3 + 1 == q["quarter"]][:2]
        out.append({"label": q["label"], "text": f"임직원 {q['headcount']}명, 고객사 {q['customers']}곳, 분기 매출 {q['revenue_eok']}억원. 안건: {TOWNHALL_TOPICS[i % len(TOWNHALL_TOPICS)]}"
                                               + (f". 이번 분기 소식: {', '.join(hi)}" if hi else "")})
    return out


def hires_by_dept(users: dict, year: int) -> list:
    n = {}
    for u in users.values():
        if u["hire_date"][:4] == str(year):
            n[u["dept"]] = n.get(u["dept"], 0) + 1
    return sorted(({"dept": d, "count": c} for d, c in n.items()), key=lambda r: -r["count"])


def year_summary(users: dict, customers: list, year: int) -> dict:
    qs = [q for q in quarters(users, customers) if q["year"] == year]
    last = qs[-1] if qs else None
    evs = [e for e in events_all(users, customers) if e["month"][:4] == str(year)]
    pms = [dict(date=d, severity=s, title=t, impact=i, cause=c, fix=f, unit=u) for d, s, t, i, c, f, u in POSTMORTEMS if d[:4] == str(year)]
    return {"year": year, "quarters": qs, "headcount": last["headcount"] if last else 0, "customers": last["customers"] if last else 0,
            "revenue_eok": round(sum(q["revenue_eok"] for q in qs), 1), "p1": sum(q["p1"] for q in qs), "p2": sum(q["p2"] for q in qs),
            "hires": hires_by_dept(users, year), "hired": sum(1 for u in users.values() if u["hire_date"][:4] == str(year)),
            "events": evs, "postmortems": pms, "townhalls": [t for t in townhalls(quarters(users, customers), events_all(users, customers)) if t["label"].startswith(str(year))],
            "in_progress": year == NOW.year}


def years(users: dict, customers: list) -> list:
    return [year_summary(users, customers, y) for y in range(FIRST_YEAR, NOW.year + 1)]
