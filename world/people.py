"""Nowhere's roster: org structure + people, generated deterministically (seeded), so every run has the same company.

All names are random combinations of common Korean surnames and given names and refer to no real person.
The 13 demo accounts (featured=True) keep their ids and are placed inside the org like everyone else.
"""
import random
from datetime import date, timedelta

SURNAMES = [("김", "kim"), ("이", "lee"), ("박", "park"), ("최", "choi"), ("정", "jung"), ("강", "kang"), ("조", "cho"), ("윤", "yoon"),
            ("장", "jang"), ("임", "lim"), ("한", "han"), ("오", "oh"), ("서", "seo"), ("신", "shin"), ("권", "kwon"), ("황", "hwang"),
            ("안", "ahn"), ("송", "song"), ("류", "ryu"), ("홍", "hong"), ("전", "jeon"), ("고", "ko"), ("문", "moon"), ("양", "yang"),
            ("손", "son"), ("배", "bae"), ("백", "baek"), ("허", "heo"), ("남", "nam"), ("노", "no")]
GIVEN = [("민수", "minsu"), ("서연", "seoyeon"), ("지훈", "jihoon"), ("하준", "hajun"), ("서윤", "seoyun"), ("도윤", "doyun"), ("지우", "jiwoo"),
         ("예준", "yejun"), ("수아", "sua"), ("시우", "siwoo"), ("하은", "haeun"), ("주원", "juwon"), ("지민", "jimin"), ("유진", "yujin"),
         ("현우", "hyunwoo"), ("서진", "seojin"), ("건우", "geonwoo"), ("다은", "daeun"), ("은서", "eunseo"), ("준서", "junseo"),
         ("채원", "chaewon"), ("민재", "minjae"), ("소연", "soyeon"), ("태민", "taemin"), ("지안", "jian"), ("유나", "yuna"),
         ("승현", "seunghyun"), ("나연", "nayeon"), ("재윤", "jaeyun"), ("하린", "harin"), ("동현", "donghyun"), ("예린", "yerin"),
         ("선우", "seonwoo"), ("가은", "gaeun"), ("시현", "sihyun"), ("보람", "boram"), ("성민", "seongmin"), ("혜진", "hyejin"),
         ("영호", "youngho"), ("미래", "mirae"), ("정훈", "junghoon"), ("수빈", "subin"), ("지원", "jiwon"), ("세영", "seyoung"),
         ("태양", "taeyang"), ("아린", "arin"), ("규리", "gyuri"), ("해솔", "haesol"), ("누리", "nuri"), ("한결", "hangyeol")]

HQ, RND, BUSAN = "서울 성수 본사", "판교 R&D센터", "부산 고객지원센터"

# Featured demo accounts: id, name, title as shown before, team (coarse function), role
FEATURED = {
    "u_ceo": ("최민재", "대표이사", "경영", "executive"), "u_cfo": ("정유라", "CFO", "경영", "executive"),
    "u_cto": ("박준영", "CTO", "개발", "executive"), "u_dev1": ("이서연", "백엔드 개발자", "개발", "employee"),
    "u_dev2": ("한도윤", "프론트엔드 개발자", "개발", "employee"), "u_slead": ("이정호", "영업팀장", "영업", "employee"),
    "u_kim": ("김민수", "영업 사원", "영업", "employee"), "u_sales2": ("윤지아", "영업 사원", "영업", "employee"),
    "u_legal": ("강하늘", "컴플라이언스 책임자", "컴플라이언스", "employee"), "u_comp2": ("송다은", "컴플라이언스 담당", "컴플라이언스", "employee"),
    "u_cs1": ("오세훈", "CS 팀장", "CS", "employee"), "u_cs2": ("배수진", "CS 상담원", "CS", "employee"),
    "u_hr": ("장미래", "인사 담당", "인사", "employee"),
}

# dept key, name, location, head person (featured id or None to generate), head position/grade/job, units
# unit: (name, headcount incl. the team lead, coarse team, job titles, featured placements {id: "lead"|"member"})
DEPTS = [
    dict(key="strategy", name="경영기획실", loc=HQ, head=(None, "실장", "이사", "경영기획"), units=[
        ("전략기획팀", 5, "경영", ["전략기획", "사업기획"], {}), ("IR·투자팀", 3, "경영", ["IR", "투자관리"], {})]),
    dict(key="support", name="경영지원본부", loc=HQ, head=("u_cfo", "본부장", "C-level", "최고재무책임자"), units=[
        ("재무회계팀", 8, "재무", ["회계", "재무", "세무", "자금"], {}), ("인사팀", 7, "인사", ["인사", "채용", "조직문화", "급여·보상"], {"u_hr": "member"}),
        ("총무·구매팀", 6, "인사", ["총무", "구매", "자산관리", "사무환경"], {})]),
    dict(key="legal", name="법무·컴플라이언스실", loc=HQ, head=("u_legal", "실장", "이사", "컴플라이언스 책임자"), units=[
        ("법무팀", 4, "컴플라이언스", ["사내변호사", "계약검토"], {}), ("컴플라이언스팀", 6, "컴플라이언스", ["컴플라이언스", "내부통제", "규제대응"], {"u_comp2": "member"}),
        ("정보보호팀", 5, "컴플라이언스", ["정보보호", "보안관제", "개인정보보호"], {})]),
    dict(key="product", name="제품본부", loc=HQ, head=(None, "본부장", "C-level", "최고제품책임자"), units=[
        ("제품기획팀", 8, "제품", ["프로덕트 매니저", "프로덕트 오너", "서비스기획"], {}), ("디자인팀", 6, "제품", ["프로덕트 디자이너", "UX 리서처", "UI 디자이너"], {}),
        ("데이터분석팀", 5, "제품", ["데이터 분석가", "BI 엔지니어"], {})]),
    dict(key="eng", name="개발본부", loc=RND, head=("u_cto", "본부장", "C-level", "최고기술책임자"), units=[
        ("백엔드1팀", 9, "개발", ["백엔드 엔지니어", "서버 개발자"], {"u_dev1": "member"}), ("백엔드2팀", 8, "개발", ["백엔드 엔지니어", "코어 시스템 개발자"], {}),
        ("프론트엔드팀", 7, "개발", ["프론트엔드 엔지니어", "웹 개발자"], {"u_dev2": "member"}), ("모바일팀", 6, "개발", ["iOS 엔지니어", "안드로이드 엔지니어"], {}),
        ("플랫폼·인프라팀", 7, "개발", ["SRE", "DevOps 엔지니어", "클라우드 엔지니어"], {}), ("AI·데이터팀", 9, "개발", ["ML 엔지니어", "데이터 엔지니어", "LLM 엔지니어"], {}),
        ("QA팀", 6, "개발", ["QA 엔지니어", "테스트 자동화 엔지니어"], {})]),
    dict(key="sales", name="사업본부", loc=HQ, head=(None, "본부장", "이사", "사업총괄"), units=[
        ("법인영업팀", 10, "영업", ["법인영업", "보험사 담당 영업", "영업 기획"], {"u_slead": "lead", "u_kim": "member", "u_sales2": "member"}),
        ("제휴·BD팀", 6, "영업", ["제휴 매니저", "사업개발"], {}), ("영업지원팀", 5, "영업", ["영업지원", "계약관리", "제안서 작성"], {}),
        ("고객성공팀", 7, "영업", ["고객성공 매니저", "온보딩 컨설턴트"], {})]),
    dict(key="insurance", name="보험사업본부", loc=HQ, head=(None, "본부장", "이사", "보험사업총괄"), units=[
        ("상품개발팀", 6, "보험사업", ["보험상품 기획", "상품개발"], {}), ("언더라이팅팀", 7, "보험사업", ["언더라이터", "위험평가"], {}),
        ("계리팀", 5, "보험사업", ["계리사", "리스크 계리"], {}), ("보상심사팀", 8, "보험사업", ["보상 심사역", "손해사정 지원"], {})]),
    dict(key="marketing", name="마케팅본부", loc=HQ, head=(None, "본부장", "이사", "마케팅총괄"), units=[
        ("브랜드팀", 4, "마케팅", ["브랜드 매니저", "PR"], {}), ("퍼포먼스팀", 5, "마케팅", ["퍼포먼스 마케터", "CRM 마케터"], {}),
        ("콘텐츠팀", 4, "마케팅", ["콘텐츠 에디터", "영상 PD"], {})]),
    dict(key="center", name="고객지원센터", loc=BUSAN, head=(None, "센터장", "이사", "고객지원총괄"), units=[
        ("상담1팀", 9, "CS", ["고객 상담원", "상담 파트장"], {"u_cs1": "lead", "u_cs2": "member"}), ("상담2팀", 9, "CS", ["고객 상담원", "상담 파트장"], {}),
        ("클레임팀", 7, "CS", ["클레임 전문 상담원", "민원 대응"], {})]),
]
GRADES = ["사원", "선임", "책임", "수석"]
GRADE_W = [40, 30, 20, 10]


def _ext_base(i):  # internal phone extension block per unit
    return 3000 + i * 20


def build():
    rnd = random.Random(2026)
    used_names = {v[0] for v in FEATURED.values()}
    used_emails: set[str] = set()
    people: list[dict] = []
    nid = [100]

    def new_name():
        while True:
            (s, sr), (g, gr) = rnd.choice(SURNAMES), rnd.choice(GIVEN)
            if s + g not in used_names:
                used_names.add(s + g)
                return s + g, f"{gr}.{sr}"

    def email(handle):
        h, n = handle, 1
        while f"{h}@nowhere.example" in used_emails:
            n += 1
            h = f"{handle}{n}"
        used_emails.add(f"{h}@nowhere.example")
        return f"{h}@nowhere.example"

    def hire(lo_year, hi_year):
        d0, d1 = date(lo_year, 3, 1), date(hi_year, 10, 31)
        return (d0 + timedelta(days=rnd.randint(0, (d1 - d0).days))).isoformat()

    def person(pid, name, handle, **kw):
        base = dict(id=pid, name=name, email=email(handle), employment="정규직", status="재직", featured=pid in FEATURED)
        base.update(kw)
        people.append(base)
        return base

    ceo = person("u_ceo", FEATURED["u_ceo"][0], "ceo", grade="C-level", position="대표이사", job_title="대표이사", title="대표이사", dept="경영", dept_key="ceo",
                 unit="대표이사실", team="경영", role="executive", manager_id=None, location=HQ, hire_date="2019-03-04", ext="3000")
    for di, d in enumerate(DEPTS):
        fid, hpos, hgrade, hjob = d["head"]
        if fid:
            nm, ttl, team, role = FEATURED[fid]
            head = person(fid, nm, fid.removeprefix("u_"), grade=hgrade, position=hpos, job_title=hjob, title=ttl, dept=d["name"], dept_key=d["key"],
                          unit=d["name"], team=team, role=role, manager_id="u_ceo", location=d["loc"], hire_date=hire(2019, 2020), ext=str(_ext_base(di)))
        else:
            nm, handle = new_name()
            pid = f"e{nid[0]}"; nid[0] += 1
            head = person(pid, nm, handle, grade=hgrade, position=hpos, job_title=hjob, title=hjob, dept=d["name"], dept_key=d["key"], unit=d["name"],
                          team=d["units"][0][2], role="executive" if hgrade == "C-level" else "employee", manager_id="u_ceo", location=d["loc"],
                          hire_date=hire(2019, 2021), ext=str(_ext_base(di)))
        for ui, (uname, n, team, jobs, placed) in enumerate(d["units"]):
            slots = ["lead"] + ["member"] * (n - 1)
            lead_id = None
            for fid2, kind in placed.items():  # featured people take their slot first
                nm, ttl, tm, role = FEATURED[fid2]
                is_lead = kind == "lead"
                p = person(fid2, nm, fid2.removeprefix("u_"), grade="책임" if is_lead else rnd.choice(GRADES[:3]), position="팀장" if is_lead else "팀원",
                           job_title=ttl, title=ttl, dept=d["name"], dept_key=d["key"], unit=uname, team=tm, role=role, manager_id=None, location=d["loc"],
                           hire_date=hire(2020, 2024) if is_lead else hire(2021, 2025), ext=str(_ext_base(di) + ui + 1))
                slots.remove("lead" if is_lead else "member")
                if is_lead:
                    lead_id = fid2
            made = []
            for kind in slots:
                nm, handle = new_name()
                pid = f"e{nid[0]}"; nid[0] += 1
                is_lead = kind == "lead"
                grade = rnd.choice(["책임", "수석"]) if is_lead else rnd.choices(GRADES, GRADE_W)[0]
                emp = "정규직"
                if not is_lead and grade == "사원":
                    emp = rnd.choices(["정규직", "계약직", "인턴"], [80, 14, 6])[0]
                st = rnd.choices(["재직", "육아휴직", "휴직"], [96, 2.5, 1.5])[0] if not is_lead else "재직"
                job = rnd.choice(jobs)
                p = person(pid, nm, handle, grade=grade, position="팀장" if is_lead else "팀원", job_title=job, title=f"{grade} · {job}", dept=d["name"],
                           dept_key=d["key"], unit=uname, team=team, role="employee", manager_id=None, location=d["loc"],
                           hire_date=hire(2019, 2021) if is_lead else hire(2020, 2026), employment=emp, status=st, ext=str(_ext_base(di) + ui + 1))
                made.append(p)
                if is_lead:
                    lead_id = pid
            for p in people:
                if p["dept_key"] == d["key"] and p["unit"] == uname:
                    p["manager_id"] = head["id"] if p["id"] == lead_id else lead_id
    return people


def org_summary(people):
    by = {p["id"]: p for p in people}
    depts = []
    for d in DEPTS:
        members = [p for p in people if p["dept_key"] == d["key"]]
        head = next(p for p in members if p["unit"] == d["name"])
        units = []
        for (uname, *_rest) in d["units"]:
            ms = [p for p in members if p["unit"] == uname]
            lead = next((p for p in ms if p["position"] == "팀장"), None)
            units.append({"name": uname, "headcount": len(ms), "lead_id": lead["id"] if lead else None})
        depts.append({"key": d["key"], "name": d["name"], "location": d["loc"], "head_id": head["id"], "headcount": len(members), "units": units})
    return {"ceo_id": "u_ceo", "headcount": len(people), "departments": depts}, by
