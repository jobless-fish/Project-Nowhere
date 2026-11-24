"""Tiny helpers that emit diagram-design style SVG (orthogonal connectors, masked labels, 4px grid) with the Nowhere skin.

Not part of the app. It exists so the four diagrams in this folder are reproducible:  python docs/diagrams/build.py
Rules followed (diagram-design SKILL.md section 6): orthogonal connectors only, arrows drawn before boxes, every label on an opaque paper mask
with a visible gap to its stroke, no shadows, Hangul at 12px+ in the sans face (Geist + Noto Sans KR fallback).
"""
import unicodedata
from html import escape

PAPER, PAPER2, INK, MUTED, SOFT = "#fcfaf3", "#f7f2e6", "#2b2620", "#5a5043", "#6b604f"
ACCENT, ACCENT_TINT, LINK = "#1d5bc4", "rgba(29,91,196,0.08)", "#1a6a42"
RULE = "rgba(43,38,32,0.12)"
SANS = "'Geist','Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',sans-serif"
SERIF = "'Instrument Serif','Noto Serif','Noto Serif KR',serif"
MONO = "'Geist Mono',ui-monospace,monospace"


def tw(s: str, size: float) -> float:
    """Text width: every wide/full-width character costs 1em, everything else 0.60em (style-guide width budget)."""
    return sum(size if unicodedata.east_asian_width(c) in "WF" else 0.6 * size for c in s)


def up4(v: float) -> int:
    return int(-(-v // 4) * 4)


def text(x, y, s, size=12, weight=400, fill=INK, anchor="start", family=SANS, extra=""):
    return f'<text x="{x}" y="{y}" fill="{fill}" font-family="{family}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" {extra}>{escape(s)}</text>'


KINDS = {
    "focal": (ACCENT_TINT, ACCENT, ""), "backend": ("#ffffff", INK, ""), "store": ("rgba(43,38,32,0.05)", MUTED, ""),
    "external": ("rgba(43,38,32,0.03)", "rgba(43,38,32,0.30)", ""), "input": ("rgba(90,80,67,0.10)", SOFT, ""),
    "optional": ("rgba(43,38,32,0.02)", "rgba(43,38,32,0.20)", 'stroke-dasharray="4,3"'),
}


def node(x, y, w, h, name, lines=(), kind="backend", size=14):
    """Masked node: opaque paper rect, styled box, name (sans 600) and up to three 12px sublabel lines. Raises if text overflows."""
    fill, stroke, dash = KINDS[kind]
    need = max([tw(name, size)] + [tw(l, 12) for l in lines]) + 24
    if need > w:
        raise ValueError(f"node '{name}' needs {up4(need)}px, has {w}")
    total = size + 4 + 16 * len(lines)
    top = y + (h - total) / 2 + size
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{PAPER}"/>',
           f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="{1.4 if kind == "focal" else 1}" {dash}/>',
           text(x + w / 2, round(top), name, size, 600, INK, "middle")]
    for i, l in enumerate(lines):
        out.append(text(x + w / 2, round(top + 4 + 16 * (i + 1) - 2), l, 12, 400, MUTED if i == 0 else SOFT, "middle"))
    return "\n".join(out)


def route(pts, r=8):
    """Orthogonal polyline -> path with rounded corners."""
    d = f"M{pts[0][0]},{pts[0][1]}"
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        a = min(r, abs(x1 - x0) + abs(y1 - y0) - 0, abs(x2 - x1) + abs(y2 - y1))
        a = min(r, a / 2) if a else 0
        sx, sy = (x1 > x0) - (x1 < x0), (y1 > y0) - (y1 < y0)
        ex, ey = (x2 > x1) - (x2 < x1), (y2 > y1) - (y2 < y1)
        d += f" L{x1 - sx * a},{y1 - sy * a} Q{x1},{y1} {x1 + ex * a},{y1 + ey * a}"
    d += f" L{pts[-1][0]},{pts[-1][1]}"
    return d


def arrow(pts, kind="call", r=8):
    """kind: call (muted solid) | accent | link | ret (dashed filled) | async (dashed open) | plain (no marker, hierarchy line)."""
    stroke = {"accent": ACCENT, "link": LINK}.get(kind, MUTED)
    dash = ' stroke-dasharray="4,3"' if kind in ("ret", "async") else ""
    sw = 1.6 if kind == "accent" else 1.2
    marker = {"call": "arrow", "ret": "arrow", "accent": "arrow-accent", "link": "arrow-link", "async": "arrow-open", "plain": None}[kind]
    m = f' marker-end="url(#{marker})"' if marker else ""
    return f'<path d="{route(pts, r)}" fill="none" stroke="{stroke}" stroke-width="{sw}"{dash}{m}/>'


def label(cx, cy, s, anchor="middle", weight=500, fill=MUTED, bg=PAPER):
    """12px sans label on an opaque paper mask (16px tall). (cx, cy) is the mask centre; anchor start = cx is the left edge."""
    w = up4(tw(s, 12) + 12)
    x = cx - w / 2 if anchor == "middle" else cx
    return (f'<rect x="{x}" y="{cy - 8}" width="{w}" height="16" rx="2" fill="{bg}"/>'
            + text(x + w / 2, cy + 4, s, 12, weight, fill, "middle"))


def zone(x, y, w, h, title, dashed=True):
    t = up4(tw(title, 12) + 16)
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="rgba(43,38,32,0.02)" stroke="rgba(43,38,32,0.30)" stroke-dasharray="{"6,4" if dashed else "none"}"/>'
            f'<rect x="{x + 16}" y="{y - 8}" width="{t}" height="16" fill="{PAPER}"/>'
            + text(x + 16 + t / 2, y + 4, title, 12, 500, MUTED, "middle"))


def legend(y, W, items):
    """items: [(kind, text)] horizontal strip; kind from KINDS or 'zone'."""
    out = [f'<line x1="40" y1="{y - 12}" x2="{W - 40}" y2="{y - 12}" stroke="{RULE}"/>', text(40, y + 8, "범례", 12, 600, MUTED)]
    x = 112
    for k, t in items:
        if k == "zone":
            out.append(f'<rect x="{x}" y="{y}" width="20" height="12" rx="2" fill="none" stroke="rgba(43,38,32,0.30)" stroke-dasharray="4,3"/>')
        elif k in ("call", "ret", "accent"):
            out.append(arrow([(x, y + 6), (x + 24, y + 6)], k))
        else:
            f, s, d = KINDS[k]
            out.append(f'<rect x="{x}" y="{y}" width="20" height="12" rx="2" fill="{f}" stroke="{s}" {d}/>')
        out.append(text(x + 30, y + 10, t, 12, 400, MUTED))
        x += 30 + up4(tw(t, 12)) + 28
    return "\n".join(out)


MARKERS = f'''<marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{MUTED}"/></marker>
<marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{ACCENT}"/></marker>
<marker id="arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{LINK}"/></marker>
<marker id="arrow-open" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polyline points="0 0, 8 3, 0 6" fill="none" stroke="{MUTED}" stroke-width="1.2"/></marker>'''

FONTS = ("https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600"
         "&family=Noto+Serif:ital@0;1&family=Noto+Sans+KR:wght@400;500;600&family=Noto+Serif+KR:wght@400&display=swap")


def page(slug, eyebrow, title, desc, W, H, body, summary=None):
    summ = ""
    if summary:
        summ = '<div class="notes">' + "".join(f"<p><b>{escape(a)}</b> {escape(b)}</p>" for a, b in summary) + "</div>"
    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<link href="{FONTS}" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Geist','Noto Sans KR',system-ui,sans-serif; background: {PAPER}; color: {INK}; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 3rem 2rem; }}
.frame {{ max-width: 1200px; width: 100%; }}
.diagram-container {{ width: 100%; overflow-x: auto; }}
.eyebrow {{ font-family: 'Geist Mono',ui-monospace,monospace; font-size: .66rem; font-weight: 500; letter-spacing: .18em; text-transform: uppercase; color: {MUTED}; margin-bottom: .5rem; }}
h1 {{ font-family: {SERIF}; font-size: clamp(1.5rem, 2.4vw + .75rem, 2rem); font-weight: 400; letter-spacing: -.02em; line-height: 1.15; margin-bottom: 1.5rem; }}
svg {{ width: 100%; min-width: {W}px; display: block; }}
.notes {{ display: grid; grid-template-columns: 1.1fr 1fr .9fr; gap: 12px; margin-top: 20px; }}
.notes p {{ background: #fff; border: 1px solid {RULE}; border-radius: 6px; padding: 12px 14px; font-size: .86rem; line-height: 1.55; color: {MUTED}; }}
.notes b {{ display: block; color: {INK}; font-weight: 600; margin-bottom: 2px; }}
@media (max-width: 800px) {{ .notes {{ grid-template-columns: 1fr; }} }}
@media print {{ .diagram-container {{ overflow-x: visible; }} svg {{ min-width: 0; }} }}
</style>
</head>
<body>
<div class="frame">
<p class="eyebrow">{escape(eyebrow)} · Project Nowhere</p>
<h1>{escape(title)}</h1>
<div class="diagram-container">
<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="{slug}-title {slug}-desc">
<title id="{slug}-title">{escape(title)}</title>
<desc id="{slug}-desc">{escape(desc)}</desc>
<defs>
{MARKERS}
</defs>
<rect width="100%" height="100%" fill="{PAPER}"/>
{body}
</svg>
</div>
{summ}
</div>
</body>
</html>
'''
