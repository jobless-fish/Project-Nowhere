import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { Session } from "../types";
import GhostView, { GhostFlat } from "./GhostView";
import type { GhostCtl } from "./GhostView";

type Action = { type: "point"; target: string; text: string } | { type: "navigate"; route: string };
type Msg = { role: "user" | "bot"; text: string; actions?: Action[] };
type Bubble = { text: string; i?: number; n?: number; offer?: boolean } | null;
type ChatRes = { reply: string; actions: Action[]; source: string; degraded: boolean };

const KEY_HIDDEN = "nw_ghost_hidden";
const store = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } },
  sget: (k: string) => { try { return sessionStorage.getItem(k); } catch { return null; } },
  sset: (k: string, v: string) => { try { sessionStorage.setItem(k, v); } catch { /* storage blocked */ } },
};
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
const SUGGEST = ["오늘 뭐부터 해야 해요?", "이 화면 설명해 주세요", "답장 초안은 어떻게 만들어요?", "조직도는 어디서 봐요?"];

const findTarget = (id: string): HTMLElement | null => {
  for (const el of Array.from(document.querySelectorAll<HTMLElement>(`[data-guide="${id}"]`))) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) return el;
  }
  return null;
};
const visibleTargets = () => Array.from(new Set(Array.from(document.querySelectorAll<HTMLElement>("[data-guide]")).filter((e) => e.getBoundingClientRect().width > 0).map((e) => e.dataset.guide!)));
const currentRoute = () => location.hash.replace("#/", "") || "home";

/** Where the ghost hovers so it sits beside the target without covering it. */
function placeNear(r: DOMRect, s: number, vw: number, vh: number) {
  const m = 10, gap = 14, h = s / 2;
  const cx = clamp(r.left + r.width / 2, h + m, vw - h - m), cy = clamp(r.top + Math.min(r.height / 2, 70), h + m, vh - h - m);
  const opts = [
    { x: r.right + gap + h, y: cy, ok: r.right + gap + s + m <= vw }, { x: r.left - gap - h, y: cy, ok: r.left - gap - s - m >= 0 },
    { x: cx, y: r.top - gap - h, ok: r.top - gap - s - m >= 0 }, { x: cx, y: r.bottom + gap + h, ok: r.bottom + gap + s + m <= vh },
  ];
  const pick = opts.find((o) => o.ok);
  return pick ? { x: pick.x, y: pick.y } : { x: clamp(r.right - h, h + m, vw - h - m), y: clamp(r.top + h, h + m, vh - h - m) };
}

export default function Guide({ session }: { session: Session }) {
  const [hidden, setHidden] = useState(() => store.get(KEY_HIDDEN) === "1");
  const [size, setSize] = useState(() => (window.innerWidth < 800 ? 92 : 120));
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [flat, setFlat] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([{ role: "bot", text: "안녕하세요, 노워예요. 화면에서 어디를 보면 되는지 짚어 드려요. 직접 보내거나 승인하지는 못해요." }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [bubble, setBubble] = useState<Bubble>(null);
  const [ringId, setRingId] = useState<string | null>(null);
  const [side, setSide] = useState({ v: "above", h: "right" });

  const wrap = useRef<HTMLDivElement>(null), float = useRef<HTMLDivElement>(null), ring = useRef<HTMLDivElement>(null), logEnd = useRef<HTMLDivElement>(null), inputEl = useRef<HTMLInputElement>(null);
  const ctl = useRef<GhostCtl>({ look: 0, roll: 0, vx: 0, vy: 0, speed: 0, talking: false });
  const S = useRef({ x: -200, y: -200, vx: 0, vy: 0, gx: 0, gy: 0, target: null as string | null, chat: false, lost: 0, init: false, sx: 0, sy: 0, fx: 1e9, fy: 1e9, sign: 1, total: 1 });
  const steps = useRef<{ list: Extract<Action, { type: "point" }>[]; i: number }>({ list: [], i: 0 });
  const uid = session.user.id;

  S.current.chat = chatOpen;
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)"), f = () => setReduced(mq.matches), r = () => setSize(window.innerWidth < 800 ? 92 : 120);
    mq.addEventListener("change", f); window.addEventListener("resize", r);
    return () => { mq.removeEventListener("change", f); window.removeEventListener("resize", r); };
  }, []);
  useEffect(() => { const show = () => { store.set(KEY_HIDDEN, "0"); setHidden(false); }; window.addEventListener("guide:show", show); return () => window.removeEventListener("guide:show", show); }, []);

  // ---- the flight: a soft, slightly bouncy spring, an S-shaped weave while travelling, and an endless gentle drift ----
  useEffect(() => {
    if (hidden) return;
    let raf = 0, last = performance.now(), t = 0;
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      const dt = Math.min(0.05, (now - last) / 1000); last = now; t += dt;
      const st = S.current, vw = window.innerWidth, vh = window.innerHeight;
      let tx: number | null = null;
      const el = st.target ? findTarget(st.target) : null;
      if (el) {
        st.lost = 0;
        const r = el.getBoundingClientRect(), g = placeNear(r, size, vw, vh);
        st.gx = g.x; st.gy = g.y; tx = r.left + r.width / 2;
        if (ring.current) { ring.current.style.transform = `translate(${r.left - 6}px, ${r.top - 6}px)`; ring.current.style.width = `${r.width + 12}px`; ring.current.style.height = `${r.height + 12}px`; }
      } else {
        if (st.target && (st.lost += dt) > 1.5) { st.target = null; setRingId(null); }
        const mobile = vw < 800;
        st.gx = st.chat ? (mobile ? vw - size / 2 - 14 : vw - 360 - 28 - size / 2) : vw - size / 2 - 24;
        st.gy = st.chat && mobile ? Math.max(size / 2 + 8, vh - Math.min(0.6 * vh, 520) - 80 - size / 2) : vh - size / 2 - (mobile ? 84 : 28);
      }
      if (!st.init) { st.x = st.gx; st.y = vh + size; st.init = true; }     // first arrival: float up from below the screen
      if (reduced) { st.x = st.gx; st.y = st.gy; st.vx = st.vy = 0; }
      else {
        const K = 16, C = 4.4;                                              // under-damped on purpose: it overshoots a little and settles, like drifting
        st.vx += (K * (st.gx - st.x) - C * st.vx) * dt; st.vy += (K * (st.gy - st.y) - C * st.vy) * dt;
        const sp0 = Math.hypot(st.vx, st.vy); if (sp0 > 1000) { st.vx *= 1000 / sp0; st.vy *= 1000 / sp0; }
        st.x += st.vx * dt; st.y += st.vy * dt;
      }
      // each flight bows out into a wide arc (alternating sides) that closes up exactly on arrival, so a settled ghost sits still
      if (Math.hypot(st.gx - st.fx, st.gy - st.fy) > 60) { st.fx = st.gx; st.fy = st.gy; st.sx = st.x; st.sy = st.y; st.sign = -st.sign; st.total = Math.max(1, Math.hypot(st.gx - st.x, st.gy - st.y)); }
      const fdx = st.fx - st.sx, fdy = st.fy - st.sy, fl = Math.hypot(fdx, fdy) || 1;
      const prog = clamp(1 - Math.hypot(st.gx - st.x, st.gy - st.y) / st.total, 0, 1);
      const arc = reduced ? 0 : Math.sin(prog * Math.PI) * Math.min(150, st.total * 0.16) * st.sign;
      const ax = (-fdy / fl) * arc, ay = (fdx / fl) * arc;
      const speed = Math.hypot(st.vx, st.vy);
      const nx = speed > 1 ? -st.vy / speed : 0, ny = speed > 1 ? st.vx / speed : 0;
      const weave = reduced ? 0 : Math.sin(t * 4.2) * Math.min(24, speed * 0.05);
      const dx = reduced ? 0 : Math.sin(t * 0.7) * 9 + Math.sin(t * 1.9) * 3, dy = reduced ? 0 : Math.sin(t * 1.1) * 8 + Math.sin(t * 2.3) * 2.5;
      // the anchor (bubble + buttons) follows the spring and the arc, both of which end at rest, so it holds still once it arrives; weave and drift move just the body
      const px = st.x + ax, py = st.y + ay;
      if (wrap.current) wrap.current.style.transform = `translate3d(${px - size / 2}px, ${py - size / 2}px, 0)`;
      if (float.current) float.current.style.transform = `translate3d(${nx * weave + dx}px, ${ny * weave + dy}px, 0)`;
      const c = ctl.current;
      c.vx = clamp(st.vx / 700, -1, 1); c.vy = clamp(st.vy / 700, -1, 1); c.speed = speed; c.roll = clamp(-st.vx / 2600, -0.35, 0.35);
      c.look = tx !== null ? clamp((tx - px) / 600, -0.55, 0.55) : Math.sin(t * 0.6) * 0.18;     // turns toward the target but keeps facing the user
      const v = py < size + 110 ? "below" : "above", h = px > vw / 2 ? "right" : "left";
      setSide((s) => (s.v === v && s.h === h ? s : { v, h }));
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [hidden, size, reduced]);

  // ---- pointing ----
  const clearPoint = useCallback(() => { S.current.target = null; steps.current = { list: [], i: 0 }; setRingId(null); setBubble(null); ctl.current.talking = false; }, []);
  const pointAt = useCallback(async (id: string, text: string, i?: number, n?: number) => {
    let el = findTarget(id);
    for (let k = 0; !el && k < 25; k++) { await sleep(100); el = findTarget(id); }       // wait for a page we just navigated to
    if (!el) { setBubble({ text: "지금 화면에서는 그곳을 찾지 못했어요." }); return false; }
    el.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
    S.current.target = id; S.current.lost = 0; setRingId(id); setBubble({ text, i, n }); ctl.current.talking = true;
    setTimeout(() => { ctl.current.talking = false; }, 1800);
    return true;
  }, [reduced]);
  const showStep = useCallback((i: number) => { const s = steps.current.list[i]; if (!s) { clearPoint(); return; } steps.current.i = i; void pointAt(s.target, s.text, i, steps.current.list.length); }, [pointAt, clearPoint]);
  const run = useCallback(async (actions: Action[]) => {
    const pts: Extract<Action, { type: "point" }>[] = [];
    for (const a of actions) {
      if (a.type === "navigate") { window.location.hash = `#/${a.route}`; await sleep(350); } else pts.push(a);
    }
    steps.current = { list: pts, i: 0 };
    if (pts.length) showStep(0); else { S.current.target = null; setRingId(null); }
  }, [showStep]);

  // ---- greeting, and the offer to walk through today's briefing ----
  useEffect(() => {
    if (hidden || store.sget("nw_ghost_hello")) return;
    store.sset("nw_ghost_hello", "1");
    const a = setTimeout(() => setBubble({ text: "안녕하세요, 노워예요. 궁금한 게 있으면 저를 눌러 물어보세요." }), 1500);
    const b = setTimeout(() => setBubble((x) => (x && !x.offer && x.n === undefined ? null : x)), 9000);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [hidden]);
  useEffect(() => {
    const ready = () => {
      const k = `nw_tour_${uid}_${new Date().toDateString()}`;
      if (store.sget(k)) return;
      store.sset(k, "1"); setBubble({ text: "오늘 브리핑을 같이 훑어볼까요?", offer: true });
    };
    window.addEventListener("guide:briefing-ready", ready);
    return () => window.removeEventListener("guide:briefing-ready", ready);
  }, [uid]);
  const startTour = async () => {
    try {
      const r = await api.get<{ steps: Extract<Action, { type: "point" }>[] }>(`/assistant/guide/tour?user_id=${uid}`);
      const list = r.steps.filter((s) => findTarget(s.target));
      if (!list.length) { setBubble({ text: "지금 화면에서는 짚을 곳이 없어요. 홈 화면에서 다시 불러 주세요." }); return; }
      steps.current = { list, i: 0 }; showStep(0);
    } catch { setBubble({ text: "안내를 불러오지 못했어요." }); }
  };

  // ---- chat ----
  useEffect(() => { logEnd.current?.scrollIntoView({ block: "end" }); }, [msgs, busy, chatOpen]);
  useEffect(() => { if (chatOpen) inputEl.current?.focus(); }, [chatOpen]);
  const send = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setInput(""); setBusy(true);
    const next: Msg[] = [...msgs, { role: "user", text: q }];
    setMsgs(next);
    try {
      const r = await api.post<ChatRes>("/assistant/guide/chat", { user_id: uid, message: q, route: currentRoute(), targets: visibleTargets(), history: next.slice(-7, -1).map(({ role, text: t }) => ({ role, text: t })) });
      setMsgs([...next, { role: "bot", text: r.reply, actions: r.actions }]);
      ctl.current.talking = true; setTimeout(() => { ctl.current.talking = false; }, 1500);
      if (r.actions.length) await run(r.actions);
    } catch (e) {
      const wait = e instanceof ApiError && e.status === 429;
      setMsgs([...next, { role: "bot", text: wait ? "잠깐만요, 너무 빨라요. 조금 뒤에 다시 물어봐 주세요." : "지금은 대답하기 어려워요. 잠시 뒤에 다시 해 주세요." }]);
    }
    setBusy(false);
  };
  const hide = () => { store.set(KEY_HIDDEN, "1"); setHidden(true); setChatOpen(false); clearPoint(); };

  if (hidden) return <div className="guide-layer"><button className="gsummon btn" onClick={() => window.dispatchEvent(new Event("guide:show"))} aria-label="노워를 다시 부르기" title="노워를 다시 부르기">👻</button></div>;
  return (
    <div className="guide-layer" onKeyDown={(e) => { if (e.key === "Escape") { if (chatOpen) setChatOpen(false); else clearPoint(); } }}>
      <div className="sr-only" aria-live="polite">{bubble?.text}</div>
      {ringId && <div ref={ring} className="gring" aria-hidden="true" />}
      <div ref={wrap} className="ghost" style={{ width: size, height: size }}>
        {bubble && (
          <div className={`gbubble ${side.v} ${side.h}`} role="group" aria-label="노워의 안내">
            <p>{bubble.text}</p>
            <div className="gbtns">
              {bubble.offer && <><button className="btn primary sm" onClick={() => { setBubble(null); void startTour(); }}>둘러보기</button><button className="btn sm" onClick={() => setBubble(null)}>나중에</button></>}
              {bubble.n !== undefined && bubble.i !== undefined && <>
                {bubble.i < bubble.n - 1 ? <button className="btn primary sm" onClick={() => showStep(bubble.i! + 1)}>다음 ({bubble.i + 1}/{bubble.n})</button> : null}
                <button className="btn sm" onClick={clearPoint}>{bubble.i < bubble.n - 1 ? "그만 볼게요" : "알겠어요"}</button></>}
              {!bubble.offer && bubble.n === undefined && <button className="btn quiet sm" onClick={() => setBubble(null)}>닫기</button>}
            </div>
          </div>
        )}
        <div className="gshadow" aria-hidden="true" />
        <div ref={float} className="gfloat"><button className="gbody" onClick={() => { if (!chatOpen) setBubble((b) => (b && !b.offer && b.n === undefined ? null : b)); setChatOpen((o) => !o); }} aria-label="노워에게 말 걸기" aria-expanded={chatOpen}>
          {flat ? <GhostFlat size={size} /> : <GhostView size={size} ctl={ctl} reduced={reduced} onFail={() => setFlat(true)} />}
        </button></div>
      </div>
      {chatOpen && (
        <section className="gchat" role="dialog" aria-label="노워와 대화">
          <header><b>노워</b><span className="small muted grow">화면을 짚어 주는 안내자</span>
            <button className="btn quiet sm" onClick={hide} title="유령을 숨겨요. 사이드바에서 다시 부를 수 있어요">숨기기</button>
            <button className="btn quiet sm" onClick={() => setChatOpen(false)} aria-label="대화 닫기">닫기</button></header>
          <div className="gmsgs" role="log" aria-live="polite">
            {msgs.map((m, i) => (
              <div key={i} className={`gmsg ${m.role}`}>
                {m.text}
                {m.actions?.some((a) => a.type === "point") && <div><button className="btn sm" style={{ marginTop: 6 }} onClick={() => void run(m.actions!)}>↳ 다시 보여줘요</button></div>}
              </div>
            ))}
            {busy && <div className="gmsg bot muted" aria-label="노워가 생각 중">…</div>}
            <div ref={logEnd} />
          </div>
          <div className="gsug">{SUGGEST.map((s) => <button key={s} className="chip" onClick={() => void send(s)}>{s}</button>)}</div>
          <form className="gform" onSubmit={(e) => { e.preventDefault(); void send(input); }}>
            <input ref={inputEl} value={input} onChange={(e) => setInput(e.target.value)} placeholder="무엇이든 물어보세요" maxLength={500} aria-label="노워에게 보낼 메시지" />
            <button className="btn primary" disabled={busy || !input.trim()}>보내기</button>
          </form>
          <div className="gcredit">유령 모델 <a href="https://sketchfab.com/3d-models/ghost-game-ready-b553ea4141f34a14b654736a317610b8" target="_blank" rel="noreferrer">"Ghost Game Ready"</a> · <a href="https://sketchfab.com/barnusmodels" target="_blank" rel="noreferrer">BarnusModels</a> · <a href="http://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a></div>
        </section>
      )}
    </div>
  );
}
