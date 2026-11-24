"""Money and performance of the operating company: P&L, cash and runway, department budgets, targets, and the signals they raise.

Everything derives from the same facts the rest of the world uses (roster, customers, funding rounds in the history, incidents), so a number
here can always be traced: revenue = archive.quarters, payroll = headcount x loaded cost, cash = funding - cumulative losses.
The numbers matter operationally: `signals()` turns them into notices for the people who must act (account owner before a renewal, department
head when spend runs ahead of plan, executives when the plan is missed or runway is short). Those notices reach the assistant's briefing.
"""
import random
import zlib
from datetime import date, timedelta

from . import archive

FUNDING = [("2019-03", 4.0, "창업 자본"), ("2019-11", 20.0, "시드"), ("2020-12", 30.0, "프리 A"), ("2021-09", 90.0, "시리즈 A"), ("2023-06", 50.0, "브릿지"), ("2024-09", 180.0, "시리즈 B")]   # eok KRW; must match HISTORY
CEO_ID, CFO_ID = "u_ceo", "u_cfo"
# department program budgets for 2026 (eok KRW, non-payroll), and how much faster than plan each has been spending (hand-set, so the story is stable)
PROGRAM = {"개발본부": (14.0, 1.07), "마케팅본부": (16.0, 1.12), "사업본부": (6.0, 0.97), "보험사업본부": (3.0, 0.95), "고객지원센터": (2.5, 1.03),
           "제품본부": (2.0, 0.92), "경영지원본부": (5.0, 0.99), "경영기획실": (1.2, 0.9), "법무·컴플라이언스실": (2.2, 1.0)}
ATTAIN = {2023: .97, 2024: 1.03, 2025: .94, 2026: .91}      # revenue vs plan, by year (2026 is year to date)


def _rnd(*p):
    return random.Random(zlib.crc32("|".join(map(str, p)).encode()))


def loaded_cost(d: date) -> float:
    """Fully loaded monthly cost of one person (eok KRW): 0.034 in 2019, +5.5% a year."""
    return 0.034 * 1.055 ** ((d - date(2019, 3, 1)).days / 365.25)


def pnl(users: dict, customers: list) -> list:
    qs = archive.quarters(users, customers)
    cash, out = 0.0, []
    funding = {m: (v, n) for m, v, n in FUNDING}
    for i, q in enumerate(qs):
        end = date.fromisoformat(q["end"])
        prev = qs[i - 1]["headcount"] if i else q["headcount"]
        avg_hc = (prev + q["headcount"]) / 2
        months = 3 if not q["in_progress"] else max(1, round((end - date(q["year"], q["quarter"] * 3 - 2, 1)).days / 30))
        payroll = round(avg_hc * loaded_cost(end) * months, 1)
        infra = round(0.06 * q["revenue_eok"] + 0.004 * avg_hc * months, 1)
        marketing = round(0.05 * q["revenue_eok"] + 0.003 * avg_hc * months, 1)
        office = round(0.004 * avg_hc * months, 1)
        other = round(0.002 * avg_hc * months, 1)
        cost = round(payroll + infra + marketing + office + other, 1)
        revenue = round(q["revenue_eok"] * (months / 3), 1)
        if q["in_progress"]:
            revenue = round(q["revenue_eok"] * months / 3, 1)
        profit = round(revenue - cost, 1)
        raised = sum(v for m, (v, _) in funding.items() if date(q["year"], q["quarter"] * 3 - 2, 1).isoformat()[:7] <= m <= end.isoformat()[:7])
        cash = round(cash + profit + raised, 1)
        burn = max(0.0, -profit / months)
        out.append({"label": q["label"], "year": q["year"], "quarter": q["quarter"], "in_progress": q["in_progress"], "revenue": revenue, "payroll": payroll,
                    "infra": infra, "marketing": marketing, "other": round(office + other, 1), "cost": cost, "profit": profit, "raised": raised, "cash": cash,
                    "runway_months": round(cash / burn, 1) if burn > 0.01 else None})
    return out


def yearly_pnl(rows: list) -> list:
    ys = {}
    for r in rows:
        y = ys.setdefault(r["year"], {"year": r["year"], "revenue": 0.0, "cost": 0.0, "profit": 0.0, "raised": 0.0})
        for k in ("revenue", "cost", "profit", "raised"):
            y[k] = round(y[k] + r[k], 1)
        y["cash"] = r["cash"]
        y["in_progress"] = r["in_progress"]
    return list(ys.values())


def budgets(users: dict, today: date = archive.NOW) -> list:
    """2026 department budgets vs spending to date. Payroll plan = year-average headcount x loaded cost x 12."""
    y0 = date(today.year, 1, 1)
    elapsed = (today - y0).days / 365.0
    out = []
    depts = sorted({u["dept"] for u in users.values() if u["dept"] != "경영"})
    for d in depts:
        mem = [u for u in users.values() if u["dept"] == d]
        start = sum(1 for u in mem if u["hire_date"] < y0.isoformat())
        avg = (start + len(mem)) / 2
        payroll = round(avg * loaded_cost(date(today.year, 7, 1)) * 12, 1)
        prog, pace = PROGRAM.get(d, (1.0, 1.0))
        budget = round(payroll + prog, 1)
        actual = round(budget * elapsed * pace * (0.99 + 0.02 * _rnd("bud", d).random()), 1)
        used = actual / budget
        out.append({"dept": d, "headcount": len(mem), "budget": budget, "payroll_plan": payroll, "program_plan": prog, "actual": actual, "used": round(used, 3),
                    "pace": round(used / elapsed, 3), "over_pace": used / elapsed > 1.05, "head": next((u["id"] for u in mem if u["position"] in ("본부장", "실장", "센터장")), None)})
    return sorted(out, key=lambda r: -r["pace"])


def targets(users: dict, customers: list) -> list:
    """Plan vs actual per year (revenue, new named customers, availability)."""
    rows = pnl(users, customers)
    yr = {r["year"]: r for r in yearly_pnl(rows)}
    qs = archive.quarters(users, customers)
    out = []
    for y, att in ATTAIN.items():
        a = yr[y]["revenue"]
        plan = round(a / att, 1)
        yq = [q for q in qs if q["year"] == y]
        down = sum(q["p1"] * 90 + q["p2"] * 25 for q in yq)                     # minutes of impact: P1 ~90, P2 ~25
        span = sum((90 if not q["in_progress"] else 61) * 24 * 60 for q in yq)
        uptime = round(100 - 100 * down / span, 3)
        out.append({"year": y, "revenue_plan": plan, "revenue_actual": a, "revenue_attain": round(att, 3), "uptime_target": 99.9, "uptime_actual": uptime,
                    "uptime_ok": uptime >= 99.9, "new_customers": yq[-1]["customers"] - ([q for q in qs if q["year"] == y - 1][-1]["customers"] if y > 2019 else 0),
                    "in_progress": yr[y]["in_progress"]})
    return out


def runway(users: dict, customers: list) -> dict:
    rows = pnl(users, customers)
    cur = rows[-1]
    last3 = rows[-4:-1] if len(rows) > 3 else rows
    burn = max(0.0, -sum(r["profit"] for r in last3) / (3 * len(last3)))     # eok / month, last full quarters
    return {"cash": cur["cash"], "monthly_burn": round(burn, 1), "months": round(cur["cash"] / burn, 1) if burn > 0.01 else None}


def signals(users: dict, customers: list, now) -> list:
    """Notices that money and performance create for specific people. -> [{id,title,body,audience,hours_ago}]."""
    today = now.date() if hasattr(now, "date") else now
    out = []
    for c in customers:
        if c["kind"] != "고객사" or not c.get("renewal") or not c["owner"]:
            continue
        dd = (date.fromisoformat(c["renewal"]) - today).days
        if 0 <= dd <= 120:
            tone = "주의 계정이니 이번 주에 미팅을 잡으세요." if c["health"] == "주의" else "갱신 조건 초안을 미리 준비하세요."
            out.append({"id": f"sig_renew_{c['id']}", "title": f"[갱신] {c['name']} 계약 갱신 D-{dd}",
                        "body": f"{c['name']}({c['product']})의 연 계약 {c['annual_eok']}억원이 {c['renewal']}에 갱신됩니다. 상태: {c['health']}. {tone}",
                        "audience": f"user:{c['owner']['id']}", "hours_ago": 3 + dd % 6})
    heads = {r["dept"]: r for r in budgets(users)}
    for d, b in heads.items():
        if b["over_pace"] and b["head"]:
            body = (f"{d}의 올해 예산 {b['budget']}억원 중 {round(b['used'] * 100)}%를 썼어요. 시간이 지난 비율({round(b['used'] / b['pace'] * 100)}%)보다 앞서가는 페이스({round(b['pace'] * 100)}%)예요. "
                    f"4분기 지출 승인 전에 우선순위를 점검하고, 초과가 예상되면 CFO와 협의하세요.")
            for uid in {b["head"], CFO_ID}:
                if uid in users:
                    out.append({"id": f"sig_budget_{b['dept']}_{uid}", "title": f"[예산] {d} 지출 페이스 {round(b['pace'] * 100)}%", "body": body, "audience": f"user:{uid}", "hours_ago": 5})
    t = [x for x in targets(users, customers) if x["in_progress"]]
    if t and t[0]["revenue_attain"] < 0.95:
        x = t[0]
        out.append({"id": "sig_target_rev", "title": f"[실적] {x['year']} 매출 계획 대비 {round(x['revenue_attain'] * 100)}%",
                    "body": f"올해 매출 계획 {x['revenue_plan']}억원 대비 지금까지 {x['revenue_actual']}억원이에요. 4분기 갱신과 신규 계약 우선순위를 타운홀 전에 정리해 주세요.",
                    "audience": "role:executive", "hours_ago": 7})
    rw = runway(users, customers)
    if rw["months"] is not None and rw["months"] < 30:
        out.append({"id": "sig_runway", "title": f"[재무] 현금 {rw['cash']}억원 · 런웨이 약 {round(rw['months'])}개월",
                    "body": f"최근 분기 평균으로 월 {rw['monthly_burn']}억원씩 쓰고 있어요. 채용과 마케팅 집행 속도를 4분기 계획에 반영해야 해요.", "audience": "role:executive", "hours_ago": 9})
    return out
