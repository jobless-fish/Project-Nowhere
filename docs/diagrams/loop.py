"""Loop diagram: the feedback flywheel. Geometry follows diagram-design type-loop.md section 2 (circle arcs between stations, radial spokes)."""
import math

from dd import *  # noqa: F401,F403

C = (520, 340)
R = 240
SW, SH, HW, HH = 176, 64, 216, 104
STATIONS = [("브리핑 제안", ("할 일과 초안을 만들어요",), "backend"), ("사람이 처리", ("완료 · 제외 · 수정",), "backend"),
            ("피드백 기록", ("처리 결과가 남아요",), "backend"), ("평가 사례로", ("정답 라벨이 붙어요",), "backend"),
            ("재채점 게이트", ("기준선 아래면 차단",), "focal"), ("개선 반영", ("프롬프트·규칙 수정",), "backend")]
SPOKES = {2: "기록", 3: "사례", 4: "점수"}


def _g4(v):
    return int(round(v / 4.0) * 4)


def _ang(p):
    return math.atan2(p[1] - C[1], p[0] - C[0])


def _inter(rect):
    x0, y0, x1, y1 = rect
    pts = []
    for xe in (x0, x1):
        d = R * R - (xe - C[0]) ** 2
        if d >= 0:
            for sgn in (1, -1):
                y = C[1] + sgn * math.sqrt(d)
                if y0 - 1e-6 <= y <= y1 + 1e-6:
                    pts.append((xe, y))
    for ye in (y0, y1):
        d = R * R - (ye - C[1]) ** 2
        if d >= 0:
            for sgn in (1, -1):
                x = C[0] + sgn * math.sqrt(d)
                if x0 - 1e-6 <= x <= x1 + 1e-6:
                    pts.append((x, ye))
    return pts


def _dist(vx, vy, a, b):
    ds = [h / abs(v) for v, h in ((vx, a), (vy, b)) if abs(v) > 1e-9]
    return min(ds)


def build(write):
    n = len(STATIONS)
    rects, cent = [], []
    for k in range(n):
        th = math.radians(-90 + k * 360 / n)
        cx, cy = C[0] + R * math.cos(th), C[1] + R * math.sin(th)
        x, y = _g4(cx - SW / 2), _g4(cy - SH / 2)
        rects.append((x, y, x + SW, y + SH))
        cent.append((cx, cy, th))
    entry, exit_ = [], []
    for k in range(n):
        th = cent[k][2]
        pts = _inter(rects[k])
        rel = [((((_ang(p) - th) + math.pi) % (2 * math.pi)) - math.pi, p) for p in pts]
        entry.append(min(rel, key=lambda t: t[0])[1] if min(t[0] for t in rel) < 0 else rel[0][1])
        exit_.append(max(rel, key=lambda t: t[0])[1])
    parts = []
    for k in range(n):
        j = (k + 1) % n
        phi = _ang(entry[j]) - 1.2 / R
        end = (C[0] + R * math.cos(phi), C[1] + R * math.sin(phi))
        st = exit_[k]
        parts.append(f'<path d="M{st[0]:.3f},{st[1]:.3f} A{R},{R} 0 0 1 {end[0]:.3f},{end[1]:.3f}" fill="none" stroke="{ACCENT if k == 3 else MUTED}" stroke-width="{1.6 if k == 3 else 1.2}" marker-end="url(#{"arrow-accent" if k == 3 else "arrow"})"/>')
    A_, B_ = HW / 2, HH / 2
    for k in SPOKES:
        th = cent[k][2]
        ux, uy = math.cos(th), math.sin(th)
        dst = _dist(ux, uy, SW / 2, SH / 2)
        dh = _dist(ux, uy, A_, B_)
        sx, sy = cent[k][0] - dst * ux, cent[k][1] - dst * uy
        ex, ey = C[0] + (dh + 6) * ux, C[1] + (dh + 6) * uy
        parts.append(f'<path d="M{sx:.3f},{sy:.3f} L{ex:.3f},{ey:.3f}" fill="none" stroke="{MUTED}" stroke-width="1" stroke-dasharray="4,3" marker-end="url(#arrow)"/>')
    for k, (nm, sub, kind) in enumerate(STATIONS):
        x, y, _, _ = rects[k]
        parts.append(node(x, y, SW, SH, nm, sub, kind))
    parts.append(node(C[0] - HW // 2, C[1] - HH // 2, HW, HH, "평가 사례 저장소", ("모두가 같이 쓰는 기록", "사례가 쌓일수록 정확해져요"), "store"))
    for k, s in SPOKES.items():   # short labels beside the spokes, on masks
        th = cent[k][2]
        ux, uy = math.cos(th), math.sin(th)
        mx, my = C[0] + 150 * ux, C[1] + 150 * uy
        side = 1 if ux >= 0 else -1
        parts.append(label(mx + side * 26, my - 12 * (1 if uy > 0 else -1), s))
    parts.append(text(40, 664, "틀렸다고 눌러 준 한 번이 다음 배포의 시험 문제가 돼요.", 18, 400, MUTED, "start", SERIF, 'font-style="italic"'))
    parts.append(legend(708, 1040, [("focal", "배포를 막을 수 있는 곳"), ("backend", "단계"), ("store", "공유 기록"), ("call", "한 바퀴 흐름"), ("ret", "기록(점선)")]))
    write("feedback-loop.html", page("feedback-loop", "Loop", "피드백 루프 — 사람의 손길이 시험 문제가 돼요",
                                     "브리핑 제안, 사람의 처리, 피드백 기록, 평가 사례 변환, 재채점 게이트, 개선 반영이 평가 사례 저장소를 중심으로 도는 순환.", 1040, 772, "\n".join(parts),
                                     [("무엇이 쌓이나", "완료·관련 없음·초안 수정·반려가 평가 사례(todo / reply)로 바뀌어 저장소에 쌓여요."),
                                      ("무엇이 막나", "프롬프트나 규칙을 바꾸면 이 사례로 다시 채점하고, 기준선보다 떨어지면 CI가 배포를 막아요."),
                                      ("아직 없는 것", "실제 서비스라면 사례 수집 전에 직원 동의, 개인정보 마스킹, 보관 기간 정책이 필요해요.")]))
