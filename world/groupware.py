"""Fictional groupware document box: team documents with owner department and access lists (see acl.py).

Deterministic, template-generated, and entirely fictional: a few "anchor" documents per department with distinctive words (so the tests and the
demo can search for them), plus routine documents so the box is not empty.
"""
import random
from datetime import timedelta

# (owner dept_key, title, body, audience grants, deny, tags)
ANCHORS = [
    ("sales", "한빛손해보험 제휴 제안서 단가 협상안", "한빛손해보험과 제휴 단가를 협상한 내용입니다. 법인영업팀 목표 수수료율과 양보 가능한 하한선을 정리했습니다.", ["dept:sales"], [], ["제휴", "단가", "협상"]),
    ("sales", "2026 4분기 영업 목표와 인센티브", "사업본부 분기 목표, 팀별 인센티브 기준과 지급 시기를 안내합니다.", ["dept:sales", "role:executive"], [], ["목표", "인센티브"]),
    ("insurance", "언더라이팅 심사 기준 개정안", "고위험 고객군의 심사 기준 개정안입니다. 영업 압력과 분리해 심사팀 안에서만 논의합니다. 영업 목표를 이유로 한 예외는 허용하지 않습니다.", ["dept:insurance"], [], ["언더라이팅", "심사", "개정"]),
    ("insurance", "보상심사 사고 조사 결과 보고서", "대형 사고 건의 조사 결과와 지급 판단 근거입니다. 외부 공개 전 단계입니다.", ["unit:보상심사팀", "role:executive"], [], ["보상", "조사"]),
    ("strategy", "인수합병 후보 검토 (비공개)", "인수합병 후보 두 곳의 가치 평가와 협상 전략입니다. 공시 전까지 비공개이며 경영기획실과 대표만 열람할 수 있습니다.", ["dept:strategy"], [], ["인수합병", "M&A", "비공개"]),
    ("strategy", "내년 사업계획과 예산 배분안", "본부별 예산 배분 시나리오입니다. 확정 전 초안이므로 사본을 만들지 마세요.", ["dept:strategy", "role:executive"], [], ["예산", "사업계획"]),
    ("marketing", "겨울 캠페인 매체 예산과 성과 목표", "겨울 캠페인 채널별 예산과 목표 전환율입니다.", ["dept:marketing", "dept:sales"], [], ["캠페인", "예산"]),
    ("eng", "결제 연동 장애 사후 분석", "결제 연동 지연의 원인과 재발 방지책입니다. 전사 공유 문서입니다.", ["all"], [], ["장애", "사후분석", "결제"]),
    ("support", "급여 인상률 산정 근거 (인사팀 한정)", "연봉 협상 기준과 직급별 인상률 산정 근거입니다. 인사팀과 재무 담당 임원만 열람합니다.", ["unit:인사팀", "role:executive"], ["dept:marketing"], ["급여", "인상률"]),
    ("legal", "내부 조사 진행 현황 (컴플라이언스)", "내부 제보 건의 조사 진행 상황입니다. 컴플라이언스팀과 대표만 열람할 수 있습니다.", ["unit:컴플라이언스팀"], [], ["조사", "제보"]),
    ("legal", "개인정보 처리방침 개정 안내", "개인정보 처리방침이 개정되었습니다. 모든 직원이 읽어야 합니다.", ["all"], [], ["개인정보", "개정"]),
]
ROUTINE = ["주간 업무 보고", "회의록", "업무 매뉴얼", "자료 요청 정리", "분기 회고"]


def build(users: dict, t0) -> list[dict]:
    rnd = random.Random(23)
    docs, n = [], 0
    for owner, title, body, aud, deny, tags in ANCHORS:
        n += 1
        docs.append(dict(id=f"d{n}", kind="doc", owner=owner, title=title, body=body, audience=aud, deny=deny, tags=tags, ts=(t0 - timedelta(hours=rnd.randint(6, 400))).isoformat(timespec="seconds")))
    depts = sorted({u["dept_key"] for u in users.values()} - {"ceo"})
    for dk in depts:
        for k, r in enumerate(ROUTINE):
            n += 1
            wide = k == 2                      # manuals are shared department-wide; the rest stay inside the department
            docs.append(dict(id=f"d{n}", kind="doc", owner=dk, title=f"[{dk}] {r} {k + 1}", body=f"{dk} 부서의 {r}입니다. 내부 업무 참고용 샘플 문서예요.",
                             audience=["dept:" + dk] + (["role:executive"] if wide else []), deny=[], tags=[r], ts=(t0 - timedelta(hours=rnd.randint(6, 700))).isoformat(timespec="seconds")))
    return docs
