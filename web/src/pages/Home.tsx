import { useCallback, useEffect, useState } from "react";
import { ApiError, api, world } from "../api";
import type { Action, Briefing, Session, Todo } from "../types";
import Reply from "./Reply";
import { Badge, Card, Check, Icon, PageHead, Skeletons, SourceChip } from "../ui";

const greet = () => { const h = new Date().getHours(); return h < 11 ? "좋은 아침입니다" : h < 18 ? "안녕하세요" : "수고 많으셨습니다"; };
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function Home({ s }: { s: Session }) {
  const [b, setB] = useState<Briefing | null>(null);
  const [state, setState] = useState<"loading" | "idle" | "working" | "error">("loading");
  const [fb, setFb] = useState<Record<string, string>>({});
  const [acts, setActs] = useState<Record<string, Action>>({});
  const [drafting, setDrafting] = useState("");
  const [why, setWhy] = useState("");
  const uid = s.user.id;

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
    setFb({ ...fb, [t.key]: next });
    if (next) await api.post("/assistant/feedback", { user_id: uid, todo_key: t.key, value: next }).catch(() => {});
  };

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

  const open = b.todos.filter((t) => fb[t.key] !== "done" && fb[t.key] !== "wrong");
  const urgent = open.filter((t) => t.priority === "high");
  const normal = open.filter((t) => t.priority !== "high");
  const closed = b.todos.filter((t) => !open.includes(t));
  const firstKey = (urgent[0] ?? normal[0])?.key;
  const row = (t: Todo) => (
    <Card key={t.key} kind={t.priority === "high" ? "urgent" : "accent"} guide={t.key === firstKey ? "first-todo" : undefined}>
      <div className={`todo ${fb[t.key] === "done" ? "done" : ""}`}>
        <Check on={fb[t.key] === "done"} label={`${t.title} 완료`} onChange={() => mark(t, "done")} />
        <div className="grow stack" style={{ gap: 6 }}>
          <div className="row wrap" style={{ gap: 8 }}>
            {t.priority === "high" && <Badge kind="urgent">긴급</Badge>}
            <b className="title">{t.title}</b>{t.due && <span className="small muted">기한 {t.due}</span>}
          </div>
          <p className="small muted">{t.reason}</p>
          <div className="row wrap" style={{ gap: 6 }}>{t.source_ids.map((id) => <SourceChip key={id} id={id} sources={b.sources} />)}</div>
          {t.source_ids.some((id) => b.sources[id]?.source === "mail") &&
            <Reply uid={uid} action={acts[t.key]} busy={drafting === t.key} onPropose={() => propose(t)} onChanged={load} />}
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
        {b.fyi.length > 0 && <section data-guide="fyi"><h2>참고만 하세요</h2><Card kind="flat"><div className="stack">
          {b.fyi.map((f) => <div key={f.title} className="row wrap"><span className="grow">{f.title}</span>{f.source_ids.map((id) => <SourceChip key={id} id={id} sources={b.sources} />)}</div>)}</div></Card></section>}
        {closed.length > 0 && <p className="small faint">처리했거나 제외한 항목 {closed.length}건 — 제외한 항목은 비서 개선에 사용됩니다.</p>}
      </div>
    </>
  );
}
