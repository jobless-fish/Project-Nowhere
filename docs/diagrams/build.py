"""Builds the four Project Nowhere diagrams into docs/diagrams/*.html.   python docs/diagrams/build.py
Org-chart numbers come from the live roster (world/people.py), so the picture cannot drift from the data."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from dd import *  # noqa: E402,F401,F403
from world.store import store  # noqa: E402

OUT = Path(__file__).parent


def write(name, html):
    (OUT / name).write_text(html, encoding="utf-8")
    print("wrote", name)


# --------------------------------------------------------------------------------------------- 1. org chart
def org():
    store.reset()
    U = list(store.users.values())
    heads = {u["dept"]: u for u in U if u["position"] in ("본부장", "실장", "센터장")}
    ceo = next(u for u in U if u["position"] == "대표이사")

    def info(dept):
        h = heads[dept]
        n = sum(1 for u in U if u["dept"] == dept)
        teams = {u["unit"] for u in U if u["dept"] == dept and u["unit"] != dept}
        site = h["location"].replace("서울 ", "").replace("경기 ", "") if h.get("location") else ""
        return h, n, len(teams), site

    zones = [("경영·지원", ["경영기획실", "경영지원본부", "법무·컴플라이언스실"]),
             ("제품·기술·보험", ["제품본부", "개발본부", "보험사업본부"]),
             ("사업·고객", ["사업본부", "마케팅본부", "고객지원센터"])]
    W, H = 1040, 600
    zx, zw, zy, nh = [40, 370, 700], 300, 164, 72
    parts = []
    drops = [x + 16 for x in zx]
    # connectors first (plain hierarchy lines, no heads)
    parts.append(f'<path d="M520,100 V140" fill="none" stroke="{MUTED}" stroke-width="1.2"/>')
    parts.append(f'<path d="M{drops[0]},140 H{drops[2]}" fill="none" stroke="{MUTED}" stroke-width="1.2"/>')
    for z, (title, depts) in enumerate(zones):
        ys = [zy + 24 + i * (nh + 12) for i in range(3)]
        last = ys[-1] + nh / 2
        parts.append(f'<path d="M{drops[z]},140 V{last}" fill="none" stroke="{MUTED}" stroke-width="1.2"/>')
        for y in ys:
            parts.append(f'<path d="M{drops[z]},{y + nh / 2} H{zx[z] + 36}" fill="none" stroke="{MUTED}" stroke-width="1.2"/>')
    for z, (title, depts) in enumerate(zones):
        parts.append(zone(zx[z], zy, zw, 24 + 3 * nh + 2 * 12 + 16, title))
    total = 0
    for z, (title, depts) in enumerate(zones):
        for i, d in enumerate(depts):
            h, n, nt, site = info(d)
            total += n
            y = zy + 24 + i * (nh + 12)
            parts.append(node(zx[z] + 36, y, 248, nh, f"{d} · {n}명", (f"{h['position']} {h['name']}", f"{nt}개 팀" + (f" · {site}" if site else "")),
                              "focal" if d == "개발본부" else "backend"))
    parts.append(node(380, 36, 280, 64, f"대표이사 {ceo['name']}", (f"전체 {len(U)}명 · 9개 본부·실",), "backend"))
    parts.append(text(40, 496, "구역은 읽기 편하게 묶은 것이에요. 아홉 곳의 장은 모두 대표에게 직접 보고해요.", 18, 400, MUTED, "start", SERIF, 'font-style="italic"'))
    parts.append(legend(544, W, [("focal", "데모 계정 이서연이 속한 본부"), ("backend", "본부·실"), ("zone", "보기 편한 묶음(보고 단계 아님)")]))
    teams = sum(1 for _ in {u["unit"] for u in U if u["unit"] != u["dept"]})
    write("org-chart.html", page("org-chart", "Org chart", "노웨어 조직도 — 217명, 9개 본부·실",
                                  "대표이사 아래 아홉 개 본부·실이 직접 보고하는 노웨어의 조직 구조.", W, H, "\n".join(parts),
                                  [("규모", f"임직원 {len(U)}명, 본부·실 9개, 팀 {teams}개. 근무지는 성수 본사 · 판교 R&D센터 · 부산 고객지원센터."),
                                   ("보고 체계", "모든 구성원은 대표까지 끊김 없이 이어져요. 테스트(tests/test_roster.py)가 이 불변식을 지켜요."),
                                   ("데모 계정", "로그인 화면의 13명은 이 조직의 제자리에 배치돼 있고, 나머지 204명은 전체 업무 트래픽을 받아요.")]))
    assert total == len(U) - 1, (total, len(U))


# --------------------------------------------------------------------------------------------- 2. architecture
def architecture():
    W, H = 1080, 620
    p = []
    zone_box = (232, 84, 604, 316)
    # arrows first
    p.append(arrow([(120, 148), (120, 52), (692, 52), (692, 148)], "link"))                       # browser -> world (own token)
    p.append(arrow([(200, 172), (260, 172)], "call"))                                             # browser -> assistant api
    p.append(arrow([(456, 168), (592, 168)], "link"))                                             # assistant -> world
    p.append(arrow([(592, 192), (456, 192)], "async"))                                            # signed webhook back
    p.append(arrow([(358, 212), (358, 304)], "call"))                                             # assistant -> db
    p.append(arrow([(690, 212), (690, 304)], "call"))                                             # world -> npc
    # assistant -> llm along the top of the zone, with a hop over the browser->world drop at x=692
    p.append(f'<path d="M420,148 V128 H684 a8,8 0 0 1 16,0 H912 V304" fill="none" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    p.append(arrow([(788, 336), (872, 336)], "call"))                                             # npc -> llm
    p.append(arrow([(952, 452), (952, 368)], "async"))                                            # eval -> llm
    p.append(zone(*zone_box, "server.py · 한 프로세스 · 포트 8888"))
    p.append(node(40, 140, 160, 64, "브라우저 앱", ("React + 유령 노워",), "input"))
    p.append(node(260, 140, 196, 64, "비서 API", ("/api · 브리핑·초안·가이드",), "focal"))
    p.append(node(592, 140, 196, 64, "사내 시스템", ("/world · 메일·메신저·이슈",), "backend"))
    p.append(node(260, 304, 196, 64, "SQLite", ("브리핑·처리·피드백",), "store"))
    p.append(node(592, 304, 196, 64, "동료 엔진", ("답장 최대 3개",), "backend"))
    p.append(node(872, 304, 160, 64, "LLM", ("Gemini · Claude",), "external"))
    p.append(node(872, 452, 160, 64, "평가 · CI", ("기준선 게이트",), "optional"))
    # labels (on masks, above horizontal strokes / beside vertical strokes)
    p.append(label(392, 36, "/world · 내 토큰으로 직접"))
    p.append(label(230, 160, "/api", weight=500))
    p.append(label(524, 152, "내 토큰으로 조회"))
    p.append(label(524, 212, "서명된 웹훅"))
    p.append(label(366, 258, "처리·피드백 기록", anchor="start"))
    p.append(label(698, 258, "메일·채팅 받음", anchor="start"))
    p.append(label(560, 112, "브리핑 · 초안 요청"))
    p.append(label(830, 320, "답장 문구"))
    p.append(label(960, 410, "같은 문제로 채점", anchor="start"))
    p.append(text(232, 436, "서로는 진짜 HTTP로 통신해요. 권한은 사내 시스템이 사용자 본인 토큰으로 강제해요.", 18, 400, MUTED, "start", SERIF, 'font-style="italic"'))
    p.append(legend(560, W, [("focal", "비서(제품의 핵심)"), ("backend", "사내 시스템·엔진"), ("store", "저장소"), ("external", "외부 모델"), ("optional", "배포 전 점검"), ("zone", "프로세스 경계")]))
    write("architecture.html", page("architecture", "Architecture", "시스템 구조 — 한 프로세스, 실제 HTTP 경계",
                                    "브라우저 앱, 비서 API, 사내 시스템, 동료 엔진이 한 프로세스에서 HTTP로 통신하고 외부 LLM과 평가가 붙는 구조.", W, H, "\n".join(p),
                                    [("분리 가능", "같은 코드를 둘로 나눠 띄울 수도 있어요. 서로 부르는 주소만 바꾸면 돼요."),
                                     ("모델은 교체 가능", "LLM_PROVIDER 하나로 mock · Gemini · Claude를 바꿔요. 키가 없으면 규칙 기반으로 동작해요."),
                                     ("점검은 코드 옆에", "평가셋과 CI 게이트가 같은 저장소에 있어 프롬프트를 바꾸면 곧바로 재채점돼요.")]))


# --------------------------------------------------------------------------------------------- 3. sequence
def sequence():
    W, H = 1080, 868
    X = {"u": 120, "hr": 330, "a": 540, "w": 750, "l": 960}
    names = {"u": ("직원", "브라우저"), "hr": ("근태", "서명된 웹훅"), "a": ("비서 API", "/api"), "w": ("사내 시스템", "메일·이슈·공지"), "l": ("LLM", "모델")}
    p = []
    bottom = 748
    for k, x in X.items():
        p.append(f'<line x1="{x}" y1="104" x2="{x}" y2="{bottom}" stroke="rgba(43,38,32,0.30)" stroke-dasharray="4,4"/>')
    # opt frame (human approval) drawn before messages
    p.append('<rect x="72" y="548" width="780" height="180" rx="4" fill="rgba(43,38,32,0.02)" stroke="rgba(43,38,32,0.22)"/>')
    p.append(f'<rect x="72" y="548" width="40" height="16" rx="2" fill="{PAPER}" stroke="rgba(43,38,32,0.22)"/>' + text(92, 560, "OPT", 8, 500, MUTED, "middle", MONO, 'letter-spacing="0.12em"'))
    p.append(text(120, 561, "[사람이 승인하면]", 12, 500, MUTED))

    def msg(y, a, b, s, kind="call", lab=None, bg=PAPER):
        xa, xb = X[a], X[b]
        pts = [(xa + (0 if xb > xa else 0), y), (xb, y)]
        p.append(arrow(pts, kind))
        cx = lab if lab else (xa + xb) / 2
        p.append(label(cx, y - 14, s, weight=600 if kind == "accent" else 500, fill=ACCENT if kind == "accent" else MUTED, bg=bg))

    msg(148, "u", "hr", "출근 도장")
    msg(196, "hr", "a", "서명된 웹훅 (HMAC)", "async")
    msg(244, "a", "w", "내 토큰으로 조회", "link")
    msg(292, "w", "a", "항목 목록", "ret")
    msg(348, "a", "l", "본문은 데이터로만 전달", "call", 640)
    msg(396, "l", "a", "할 일 JSON", "ret", 640)
    # self message: validation
    y = 440
    p.append(f'<path d="M540,{y} H564 Q572,{y} 572,{y + 8} V{y + 16} Q572,{y + 24} 564,{y + 24} H548" fill="none" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    p.append(label(588, y + 12, "근거 없는 항목 버림 · 피싱 격리", anchor="start"))
    msg(512, "a", "u", "오늘의 브리핑", "accent", 440)
    msg(596, "u", "a", "초안 확인 후 보내기", "call", 232, bg="#f9f7ef")
    msg(644, "a", "w", "메일 발송 · 내 토큰", "link", bg="#f9f7ef")
    msg(692, "w", "a", "발송됨", "ret", bg="#f9f7ef")
    for k, x in X.items():
        n, s = names[k]
        p.append(node(x - 80, 32, 160, 64, n, (s,), "focal" if k == "a" else "input" if k == "u" else "external" if k == "l" else "backend"))
    p.append(text(72, 780, "발송은 사람이 누를 때만 일어나요. 어떤 단계에서도 AI가 혼자 메일을 보내지 않아요.", 18, 400, MUTED, "start", SERIF, 'font-style="italic"'))
    p.append(legend(820, W, [("focal", "비서"), ("call", "호출"), ("ret", "응답(점선)"), ("accent", "핵심 결과")]))
    write("sequence.html", page("sequence", "Sequence", "출근 도장에서 답장 발송까지",
                                 "출근 도장이 서명된 웹훅으로 비서를 깨우고, 비서가 사내 시스템과 LLM으로 브리핑을 만든 뒤, 사람이 승인해야 메일이 발송되는 순서.", W, H, "\n".join(p),
                                 [("깨우는 법", "출근 도장 시스템이 HMAC으로 서명한 웹훅을 보내요. 서명이 틀리면 비서는 움직이지 않아요."),
                                  ("믿지 않는 입력", "메일·채팅 본문은 지시가 아니라 데이터로만 모델에 줘요. 근거 id가 없는 할 일은 버려요."),
                                  ("사람이 마지막", "초안은 제안일 뿐이고, 외부 수신자는 한 번 더 확인해야 보내져요.")]))


if __name__ == "__main__":
    org()
    architecture()
    sequence()
    try:
        from loop import build as loop_build
        loop_build(write)
    except ImportError:
        pass
