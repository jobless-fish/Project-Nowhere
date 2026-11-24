import { useCallback, useEffect, useState } from "react";
import { ApiError, api, errText, world } from "../api";
import type { Action, Briefing, MuteRule, Session, Todo } from "../types";
import Reply from "./Reply";
import { Badge, Card, Icon, PageHead, Skeletons, SourceChip } from "../ui";
import { useLive } from "../live";

const greet = () => { const h = new Date().getHours(); return h < 11 ? "좋은 아침입니다" : h < 18 ? "안녕하세요" : "수고 많으셨습니다"; };
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function Home({ s }: { s: Session }) {
  const [b, setB] = useState<Briefing | null>(null);
  const [state, setState] = useState<"loading" | "idle" | "working" | "error">("loading");
  const [fb, setFb] = useState<Record<string, string>>({});
  const [acts, setActs] = useState<Record<string, Action>>({});
  const [drafting, setDrafting] = useState("");
  const [why, setWhy] = useState("");
  const [openNote, setOpenNote] = useState<{ key: string; how: "done" | "no_reply" } | null>(null);
  const [note, setNote] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const [msg, setMsg] = useState<{ key: string; text: string } | null>(null);
  const uid = s.user.id;
  const live = useLive();
  const [mutes, setMutes] = useState<MuteRule[]>([]);

  const load = useCallback(async () => {
    try {
      setB(await api.get<Briefing>(`/assistant/briefing?user_id=${uid}`));
      setFb(await api.get<Record<string, string>>(`/assistant/feedback?user_id=${uid}`));
      const list = await api.get<Action[]>(`/assistant/actions?user_id=${uid}`).catch(() => [] as Action[]);
      setActs(Object.fromEntries([...list].reverse().map((a) => [a.todo_key, a])));
      setState("idle");
      window.dispatchEvent(new Event("guide:briefing-ready"));
    } catch (e) { if (e instanceof ApiError && e.status === 404) { setB(null); setState("idle"); } else setState("error"); }
  }, [uid]);
  useEffect(() => { setState("loading"); load(); }, [load]);
  useEffect(() => { const f = () => { void load(); }; window.addEventListener("briefing:changed", f); return () => window.removeEventListener("briefing:changed", f); }, [load]);

  const act = async (t: Todo, what: "start" | "complete" | "reopen", extra: { note?: string; how?: string } = {}) => {
    setBusyKey(t.key); setMsg(null);
    try {
      await api.post(`/assistant/todos/${t.key}/${what}`, { user_id: uid, ...extra });
      setOpenNote(null); setNote("");
      await load();
      live.toast({ kind: "ok", text: what === "start" ? "작업을 시작했어요. 이슈 상태가 '진행 중'으로 바뀌었어요." : what === "reopen" ? "다시 열었어요." : "처리했어요. 아래 '처리한 일'에서 결과를 볼 수 있어요." });
    } catch (e) { setMsg({ key: t.key, text: errText(e) }); }
    setBusyKey("");
  };
  const refresh = async () => {
    try { const r = await api.post<{ new: string[] }>("/assistant/briefing/refresh", { user_id: uid }); await load(); live.toast({ kind: "ok", text: r.new.length ? `새 할 일 ${r.new.length}건을 찾았어요.` : "새로 생긴 할 일은 없어요." }); }
    catch { live.toast({ kind: "warn", text: "브리핑을 갱신하지 못했어요." }); }
  };

  // Clock in at the attendance system; it notifies the assistant by webhook. Fall back to a direct call if it is slow.
  const clockIn = async () => {
    setState("working");
    try {
      await world.post("/hr/clock-in", {}, s);
      for (let i = 0; i < 8; i++) { await sleep(600); try { await api.get<Briefing>(`/assistant/briefing?user_id=${uid}`); await load(); return; } catch { /* not ready */ } }
      await api.post("/assistant/clock-in", { user_id: uid });
      await load();   // reload briefing, feedback AND any pre-drafted replies
    } catch {
      setState("error");
      api.get<{ ok: boolean; error: string | null }>("/assistant/diag")
        .then((d) => setWhy(d.ok ? "서버는 정상이에요. 잠시 뒤에 다시 눌러 보세요." : `서버가 사내 시스템에 연결하지 못했어요. (${d.error})`))
        .catch(() => setWhy("서버에 닿지 않아요. 서버가 켜져 있는지, 주소의 포트가 맞는지 확인해 주세요."));
    }
  };
  const propose = async (t: Todo) => {
    setDrafting(t.key);
    try { const a = await api.post<Action>("/assistant/actions/propose", { user_id: uid, todo_key: t.key }); setActs((m) => ({ ...m, [t.key]: a })); }
    catch { /* not a mail todo or already handled */ }
    setDrafting("");
  };
  const mark = async (t: Todo, value: string) => {
    const next = fb[t.key] === value ? "" : value;
    if (!next) { setFb({ ...fb, [t.key]: "" }); return; }
    setMsg(null);
    try {
      const r = await api.post<{ muted: string[] }>("/assistant/feedback", { user_id: uid, todo_key: t.key, value: next });
      setFb({ ...fb, [t.key]: next });
      if (value === "wrong" && r.muted.length) {
        live.toast({ kind: "ok", text: "이런 종류의 항목은 앞으로 이 목록에 올리지 않을게요.", actions: [{ label: "되돌리기", run: () => { void undo(r.muted); } }] });
        void loadMutes();
      }
    } catch (e) { setMsg({ key: t.key, text: errText(e, "표시하지 못했어요. 잠시 뒤에 다시 해 주세요.") }); }
  };
  const loadMutes = useCallback(async () => { setMutes((await api.get<{ items: MuteRule[] }>(`/assistant/mutes?user_id=${uid}`).catch(() => ({ items: [] }))).items); }, [uid]);
  const undo = async (sigs: string[]) => {
    for (const sig of sigs) await api.post("/assistant/mutes/remove", { user_id: uid, sig }).catch(() => {});
    await api.post("/assistant/briefing/refresh", { user_id: uid }).catch(() => {});
    await Promise.all([load(), loadMutes()]);
  };
  useEffect(() => { void loadMutes(); }, [loadMutes]);

  if (state === "loading") return <><PageHead title="홈" /><Skeletons /></>;
  if (!b) return (
    <>
      <PageHead title="홈" />
      <div className="hero">
        <h1>{greet()}, {s.user.name}님</h1>
        <p>출근을 기록하면 비서가 밤새 도착한 메일과 이슈를 읽고, 오늘 할 일을 정리해 드려요.</p>
        <button className="btn primary" data-guide="clock-in" onClick={clockIn} disabled={state === "working"} aria-busy={state === "working" || undefined}>
          <Icon n="clock" />출근하기</button>
        {state === "error" && <p role="alert" style={{ color: "var(--danger)", fontWeight: 600 }}>연결에 문제가 있어요. {why || "원인을 확인하는 중…"} 다시 시도하려면 위 버튼을 눌러 주세요.</p>}
      </div>
    </>
  );

  const finished = (t: Todo) => t.flow?.status === "done" || fb[t.key] === "done";
  const dropped = (t: Todo) => fb[t.key] === "wrong";
  const open = b.todos.filter((t) => !finished(t) && !dropped(t));
  const done = b.todos.filter((t) => finished(t) && !dropped(t));
  const urgent = open.filter((t) => t.priority === "high");
  const normal = open.filter((t) => t.priority !== "high");
  const firstKey = (urgent[0] ?? normal[0])?.key;
  const KIND_KO: Record<string, string> = { mail: "메일", issue: "이슈", notice: "공지" };
  const actions = (t: Todo) => {
    const busy = busyKey === t.key, k = t.kind ?? "other";
    const noteBox = (how: "done" | "no_reply", label: string, ph: string, min = 2) => (
      <div className="stack" style={{ gap: 8 }}>
        <label className="small muted" htmlFor={`n${t.key}`}>{label}</label>
        <input id={`n${t.key}`} autoFocus value={note} placeholder={ph} maxLength={300} onChange={(e) => setNote(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && note.trim().length >= min) void act(t, "complete", { note, how }); if (e.key === "Escape") setOpenNote(null); }} />
        <div className="row"><button className="btn primary sm" disabled={busy || note.trim().length < min} onClick={() => act(t, "complete", { note, how })}>처리 완료</button>
          <button className="btn quiet sm" onClick={() => setOpenNote(null)}>취소</button></div>
      </div>);
    if (openNote?.key === t.key) return openNote.how === "no_reply" ? noteBox("no_reply", "회신하지 않는 이유", "예) 참고용 안내라 회신이 필요 없어요") : noteBox("done", "무엇을 했나요? (이슈에 기록돼요)", "예) 원인 수정 후 배포 완료");
    const go = (how: "done" | "no_reply") => { setNote(""); setOpenNote({ key: t.key, how }); };
    if (k === "issue") return t.flow?.status === "in_progress"
      ? <div className="row wrap"><Badge kind="accent">진행 중</Badge><button className="btn primary sm" disabled={busy} onClick={() => go("done")}>해결 처리…</button></div>
      : <div><button className="btn sm" disabled={busy} onClick={() => act(t, "start")}>작업 시작</button></div>;
    if (k === "notice") return <div><button className="btn primary sm" disabled={busy} onClick={() => act(t, "complete", {})}>확인했어요</button></div>;
    if (k === "mail") return <div className="stack" style={{ gap: 8 }}>
      <Reply uid={uid} action={acts[t.key]} busy={drafting === t.key} onPropose={() => propose(t)} onChanged={load} />
      <div><button className="btn quiet sm" onClick={() => go("no_reply")}>답장 없이 처리…</button></div></div>;
    return <div><button className="btn sm" disabled={busy} onClick={() => mark(t, "done")}>완료로 표시</button></div>;
  };
  const row = (t: Todo) => (
    <Card key={t.key} kind={t.priority === "high" ? "urgent" : "accent"} guide={t.key === firstKey ? "first-todo" : undefined}>
      <div className="todo">
        <div className="grow stack" style={{ gap: 8 }}>
          <div className="row wrap" style={{ gap: 8 }}>
            {t.priority === "high" && <Badge kind="urgent">긴급</Badge>}{t.kind && KIND_KO[t.kind] && <Badge>{KIND_KO[t.kind]}</Badge>}
            <b className="title">{t.title}</b>{t.due && <span className="small muted">기한 {t.due}</span>}
          </div>
          <p className="small muted">{t.reason}</p>
          <div className="row wrap" style={{ gap: 6 }}>{t.source_ids.map((id) => <SourceChip key={id} id={id} sources={b.sources} />)}</div>
          {actions(t)}
          {msg?.key === t.key && <p className="small" role="alert" style={{ color: "var(--danger)" }}>{msg.text}</p>}
        </div>
        <button className="btn quiet sm" onClick={() => mark(t, "wrong")} title="이 항목은 할일이 아닙니다">관련 없음</button>
      </div>
    </Card>
  );

  return (
    <>
      <PageHead title={`${greet()}, ${s.user.name}님`} sub={b.summary} guide="briefing-summary" />
      <div className="stack" style={{ gap: 20 }}>
        {b.degraded && <div className="banner" role="status"><Icon n="warn" />AI 연결 문제로 규칙 기반으로 정리했습니다. 내용이 단순할 수 있습니다.</div>}
        {b.flagged.length > 0 && <div className="banner" role="alert" data-guide="flagged"><Icon n="warn" /><div><b>보안 확인이 필요한 메시지 {b.flagged.length}건</b>
          {b.flagged.map((f) => <div key={f.id} className="small">{f.title} — {f.reason}</div>)}</div></div>}
        {urgent.length > 0 && <section data-guide="urgent"><h2>지금 처리하세요</h2><div className="stack">{urgent.map(row)}</div></section>}
        {normal.length > 0 && <section data-guide="later"><h2>오늘 안에</h2><div className="stack">{normal.map(row)}</div></section>}
        {open.length === 0 && <Card><p className="muted">남은 할일이 없습니다. 좋은 하루 보내세요.</p></Card>}
        <div><button className="btn quiet sm" onClick={refresh}>새 메일·이슈 확인하기</button></div>
        {b.fyi.length > 0 && <section data-guide="fyi"><h2>참고만 하세요</h2><Card kind="flat"><div className="stack">
          {b.fyi.map((f) => <div key={f.title} className="row wrap"><span className="grow">{f.title}</span>{f.source_ids.map((id) => <SourceChip key={id} id={id} sources={b.sources} />)}</div>)}</div></Card></section>}
        {done.length > 0 && <section data-guide="done"><h2>처리한 일 ({done.length})</h2><Card kind="flat"><div className="stack">
          {done.map((t) => <div key={t.key} className="row wrap"><Badge kind="ok">완료</Badge><span className="grow"><b>{t.title}</b><div className="small muted">{t.flow?.outcome || "완료로 표시했어요"}</div></span>
            <button className="btn quiet sm" onClick={() => (t.flow ? act(t, "reopen") : mark(t, "done"))}>다시 열기</button></div>)}</div></Card></section>}
        {mutes.length > 0 && <details className="muted-list"><summary className="small muted">내가 숨긴 종류 {mutes.length}가지 · 비서 개선에도 쓰여요</summary><div className="stack" style={{ gap: 6, marginTop: 8 }}>
          {mutes.map((m) => <div key={m.sig} className="row wrap"><span className="grow small">{m.title}</span><button className="btn quiet sm" onClick={() => undo([m.sig])}>다시 보기</button></div>)}</div></details>}
      </div>
    </>
  );
}
