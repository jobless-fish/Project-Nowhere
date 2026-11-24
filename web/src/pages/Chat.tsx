import { useCallback, useEffect, useRef, useState } from "react";
import { errText, world } from "../api";
import type { Channel, ChatMsg, Session } from "../types";
import { Avatar, Card, Empty, PageHead, Skeletons, ago } from "../ui";
import { PersonPicker } from "../people";
import type { Picked } from "../people";
import { useLive } from "../live";

export default function Chat({ s }: { s: Session }) {
  const live = useLive();
  const [chs, setChs] = useState<Channel[] | null>(null);
  const [cur, setCur] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<ChatMsg[] | null>(null);
  const [typing, setTyping] = useState(false);
  const [text, setText] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const [newDm, setNewDm] = useState(false), [pick, setPick] = useState<Picked>({ people: [], external: [] });
  const end = useRef<HTMLDivElement>(null), stick = useRef(true);
  // Opened from the org chart (#/chat?dm=<id>): do not flash the default channel first, and never lose the new conversation to a slower, older list response
  const wantDm = useRef(new URLSearchParams(location.hash.split("?")[1] ?? "").get("dm"));
  const [opening, setOpening] = useState(!!wantDm.current);
  const known = useRef<Channel[]>([]);

  const loadChannels = useCallback(() => world.get<Channel[]>("/chat/channels", s).then((c) => {
    const all = [...c, ...known.current.filter((k) => !c.some((x) => x.id === k.id))];     // a response that left before the DM existed must not remove it
    setChs(all);
    setCur((x) => x ?? (wantDm.current ? null : (all.find((k) => !k.dm && k.name.includes("팀")) ?? all[0])?.id ?? null));
  }).catch(() => setChs([])), [s]);
  useEffect(() => { void loadChannels(); }, [loadChannels, live.chat]);
  const curRef = useRef<string | null>(null);
  useEffect(() => { curRef.current = cur; }, [cur]);
  const loadMsgs = useCallback(async (id: string) => {
    try {
      const r = await world.get<{ items: ChatMsg[]; typing: boolean }>(`/chat/channels/${id}/messages?hours=168&limit=80&latest=true`, s);
      if (curRef.current !== id) return;           // the person already switched conversation: a late answer for the old one must not be drawn
      setMsgs(r.items); setTyping(r.typing);
    } catch { if (curRef.current === id) setMsgs([]); }
  }, [s]);
  useEffect(() => { if (cur) { setMsgs(null); stick.current = true; void loadMsgs(cur); } }, [cur, loadMsgs]);
  // while a colleague is typing, or something new arrived, refresh the open conversation
  useEffect(() => { if (cur && (live.byChannel[cur] || typing)) void loadMsgs(cur); }, [live.byChannel, cur, typing, loadMsgs]);
  useEffect(() => { if (!cur || !typing) return; const t = setInterval(() => void loadMsgs(cur), 1500); return () => clearInterval(t); }, [cur, typing, loadMsgs]);
  useEffect(() => { if (stick.current) end.current?.scrollIntoView({ block: "end" }); }, [msgs, typing]);

  useEffect(() => {
    const to = new URLSearchParams(location.hash.split("?")[1] ?? "").get("dm");
    if (!to) return;
    world.post<Channel>("/chat/dm", { to }, s).then(async (c) => {
      known.current = [...known.current.filter((k) => k.id !== c.id), c];
      await loadChannels(); setCur(c.id); wantDm.current = null; setOpening(false); history.replaceState(null, "", "#/chat");
    }).catch(() => { wantDm.current = null; setOpening(false); void loadChannels(); });
  }, [s, loadChannels]);
  const send = async () => {
    if (!cur || !text.trim() || busy) return;
    setBusy(true); setErr("");
    try { await world.post(`/chat/channels/${cur}/messages`, { text }, s); setText(""); stick.current = true; await loadMsgs(cur); setTyping(true); live.poke(); }
    catch (e) { setErr(errText(e)); }
    setBusy(false);
  };
  const startDm = async (v: Picked) => {
    setPick(v);
    const p = v.people[0]; if (!p) return;
    try { const c = await world.post<Channel>("/chat/dm", { to: p.id }, s); known.current = [...known.current.filter((k) => k.id !== c.id), c]; await loadChannels(); setCur(c.id); setNewDm(false); setPick({ people: [], external: [] }); }
    catch (e) { setErr(errText(e)); }
  };
  const current = chs?.find((c) => c.id === cur);
  const dms = chs?.filter((c) => c.dm) ?? [], chans = chs?.filter((c) => !c.dm) ?? [];
  const badge = (c: Channel) => { const n = c.id === cur ? 0 : (live.byChannel[c.id] ?? c.unread ?? 0); return n > 0 ? <span className="count" aria-label={`안 읽은 메시지 ${n}개`}>{n}</span> : null; };

  return (
    <>
      <PageHead title="메신저" sub="채널에 말을 걸거나 동료에게 직접 메시지를 보내 보세요. 동료(가상 인물)가 상황에 맞게 답해요. 답은 최대 3개까지 와요." />
      {!chs ? <Skeletons /> : (
        <div className="split">
          <Card kind="flat" guide="chat-channels"><div className="list">
            <div className="row" style={{ padding: "4px 8px" }}><span className="mono small faint grow">대화</span><button className="btn sm" onClick={() => setNewDm((v) => !v)} aria-expanded={newDm}>＋ 새 대화</button></div>
            {newDm && <div style={{ padding: 8 }}><PersonPicker s={s} label="누구에게 보낼까요?" value={pick} onChange={startDm} single autoFocus /></div>}
            {dms.map((c) => <button key={c.id} aria-current={cur === c.id} onClick={() => setCur(c.id)}><span className="row"><Avatar name={c.name} /><b className="grow trunc">{c.name}</b>{badge(c)}</span></button>)}
            <div className="mono small faint" style={{ padding: "8px 8px 0" }}>채널</div>
            {chans.map((c) => <button key={c.id} aria-current={cur === c.id} onClick={() => setCur(c.id)}><span className="row"><span className="grow trunc"># {c.name}{c.private && <span className="small faint"> · 비공개</span>}</span>{badge(c)}</span></button>)}
          </div></Card>
          <Card guide="chat-messages">
            {!current ? (opening ? <Skeletons n={2} /> : <Empty>왼쪽에서 대화를 고르거나 '새 대화'로 동료에게 말을 걸어 보세요.</Empty>) : (
              <div className="chatbox">
                <h2 style={{ marginBottom: 8 }}>{current.dm ? current.name : `# ${current.name}`}</h2>
                <div className="chatlog" role="log" aria-live="polite" onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}>
                  {!msgs ? <Skeletons n={2} /> : msgs.length === 0 ? <Empty>아직 대화가 없어요. 먼저 말을 걸어 보세요.</Empty> :
                    msgs.map((m) => { const mine = m.author.id === s.user.id; return (
                      <div key={m.id} className={`msg ${mine ? "mine" : ""}`}>{!mine && <Avatar name={m.author.name} />}
                        <div className="bubble"><div className="small muted"><b>{mine ? "나" : m.author.name}</b> · {ago(m.ts)}</div><p>{m.text}</p></div></div>); })}
                  {typing && <div className="small muted typing" role="status">동료가 입력 중<span>…</span></div>}
                  <div ref={end} />
                </div>
                <form className="composer" onSubmit={(e) => { e.preventDefault(); void send(); }}>
                  <label className="sr" htmlFor="chat-in">메시지</label>
                  <textarea id="chat-in" rows={2} value={text} maxLength={1000} placeholder={current.dm ? `${current.name}님에게 메시지 (Enter로 보내기, Shift+Enter 줄바꿈)` : "메시지를 입력하세요. 예) @팀 배포 일정 공유 부탁드려요"}
                    onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} />
                  <button className="btn primary" type="submit" disabled={!text.trim() || busy}>보내기</button>
                </form>
                {err && <p className="small" role="alert" style={{ color: "var(--danger)" }}>{err}</p>}
              </div>)}
          </Card>
        </div>)}
    </>
  );
}
