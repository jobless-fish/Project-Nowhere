import { useCallback, useEffect, useRef, useState } from "react";
import { errText, world } from "../api";
import type { Mail, Session } from "../types";
import { Badge, Card, Empty, PageHead, Skeletons, ago } from "../ui";
import { PersonPicker } from "../people";
import type { Picked } from "../people";
import { useLive } from "../live";

type Draft = { to: Picked; subject: string; body: string; ok: boolean; reply?: string };
const blank: Draft = { to: { people: [], external: [] }, subject: "", body: "", ok: false };

function Compose({ s, draft, setDraft, onSent, onClose }: { s: Session; draft: Draft; setDraft: (d: Draft) => void; onSent: () => void; onClose: () => void }) {
  const [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const ext = draft.to.external.length > 0;
  const ready = (draft.to.people.length > 0 || ext) && draft.subject.trim() && draft.body.trim() && (!ext || draft.ok);
  const send = async () => {
    setBusy(true); setErr("");
    try {
      await world.post("/mail/send", { to: draft.to.people.map((p) => p.id), to_external: draft.to.external, subject: draft.subject, body: draft.body, in_reply_to: draft.reply ?? null, confirm_external: draft.ok }, s);
      onSent();
    } catch (e) { setErr(errText(e)); }
    setBusy(false);
  };
  return (
    <Card guide="mail-compose"><div className="stack">
      <div className="row"><h2 className="grow" style={{ marginBottom: 0 }}>{draft.reply ? "답장 쓰기" : "새 메일"}</h2><button className="btn quiet sm" onClick={onClose}>닫기</button></div>
      <PersonPicker s={s} label="받는 사람" value={draft.to} onChange={(to) => setDraft({ ...draft, to })} allowExternal autoFocus={!draft.reply} />
      <label className="small muted" htmlFor="m-sub">제목</label>
      <input id="m-sub" value={draft.subject} maxLength={200} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} />
      <label className="small muted" htmlFor="m-body">본문</label>
      <textarea id="m-body" rows={8} value={draft.body} maxLength={5000} autoFocus={!!draft.reply} onChange={(e) => setDraft({ ...draft, body: e.target.value })}
        placeholder="보내면 받는 사람이 답장할 수 있어요. 답장은 최대 3통까지 도착해요." />
      {ext && <label className="row small" style={{ gap: 8 }}><input type="checkbox" style={{ width: 18 }} checked={draft.ok} onChange={(e) => setDraft({ ...draft, ok: e.target.checked })} />
        사외로 나가는 메일임을 확인했습니다</label>}
      {err && <p className="small" role="alert" style={{ color: "var(--danger)" }}>{err}</p>}
      <div className="row"><button className="btn primary" disabled={!ready || busy} aria-busy={busy || undefined} onClick={send}>보내기</button>
        {!ready && <span className="small muted">받는 사람, 제목, 본문을 채워 주세요{ext && !draft.ok ? " (외부 확인 포함)" : ""}.</span>}</div>
    </div></Card>
  );
}

export default function MailPage({ s }: { s: Session }) {
  const live = useLive();
  const [box, setBox] = useState<"in" | "sent">("in");
  const [mails, setMails] = useState<Mail[] | null>(null);
  const [sel, setSel] = useState<Mail | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [err, setErr] = useState(false);
  const latest = useRef(0);       // only the newest request may draw: an older inbox response arriving after the sent-folder one would show the wrong folder
  const load = useCallback(async (keep?: string) => {
    const mine = ++latest.current;
    try {
      const r = await world.get<{ items: Mail[] }>(`/mail/${box === "in" ? "inbox" : "sent"}?hours=72&limit=100`, s);
      if (mine !== latest.current) return;
      setMails(r.items); setErr(false);
      setSel((cur) => r.items.find((m) => m.id === (keep ?? cur?.id)) ?? r.items[0] ?? null);
      if (box === "in") void world.post("/mail/seen", {}, s).catch(() => {});
    } catch { if (mine === latest.current) setErr(true); }
  }, [s, box]);
  useEffect(() => { setMails(null); void load(); }, [load]);
  useEffect(() => { if (box === "in" && live.mail > 0) void load(); }, [live.mail, box, load]);
  useEffect(() => { // #/mail?open=<id> from a toast
    const q = new URLSearchParams(location.hash.split("?")[1] ?? ""); const id = q.get("open");
    if (id) { setBox("in"); void load(id); }
    const to = q.get("to");
    if (to) world.get<{ id: string; name: string; unit: string }>(`/directory/people/${to}`, s).then((p) => { setDraft({ ...blank, to: { people: [{ id: p.id, name: p.name, unit: p.unit }], external: [] } }); history.replaceState(null, "", "#/mail"); }).catch(() => {});
  }, [load, s]);

  const replyTo = (m: Mail) => setDraft({ ...blank, reply: m.id,
    to: m.from.id ? { people: [{ id: m.from.id, name: m.from.name }], external: [] } : { people: [], external: m.external ? [m.from.email] : [] },
    subject: m.subject.startsWith("Re:") ? m.subject : `Re: ${m.subject}`,
    body: `\n\n— ${m.from.name}님 메일 중 —\n${m.body.split("\n").map((l) => `> ${l}`).join("\n")}` });
  const sent = () => { setDraft(null); if (box !== "sent") setBox("sent"); live.toast({ kind: "ok", text: "보냈어요. 답장은 잠시 뒤 받은편지함에 도착해요." }); live.poke(); if (box === "sent") void load(); };
  const peopleOf = (m: Mail) => [...m.to_people.map((p) => p.name), ...m.to_external].join(", ");

  return (
    <>
      <PageHead title="메일" sub="노웨어 사내 메일입니다. 직접 써서 보내면 받는 사람이 직무에 맞게 답장해요 (가상 인물)." />
      <div className="row wrap" style={{ marginBottom: 16 }}>
        <button className="btn primary" data-guide="mail-new" onClick={() => setDraft({ ...blank })}>새 메일 쓰기</button>
        <div className="tabs" role="tablist" style={{ margin: 0, border: 0 }}>
          <button role="tab" aria-selected={box === "in"} onClick={() => setBox("in")}>받은편지함{live.mail > 0 && box !== "in" ? ` (${live.mail})` : ""}</button>
          <button role="tab" aria-selected={box === "sent"} onClick={() => setBox("sent")}>보낸편지함</button></div>
        {live.typing && <span className="small muted" role="status">답장을 쓰는 중…</span>}
      </div>
      {draft && <div style={{ marginBottom: 16 }}><Compose s={s} draft={draft} setDraft={setDraft} onSent={sent} onClose={() => setDraft(null)} /></div>}
      {err ? <Empty>메일을 불러오지 못했습니다.</Empty> : !mails ? <Skeletons /> : mails.length === 0 ? <Empty>{box === "in" ? "받은 메일이 없습니다." : "보낸 메일이 없어요. 위의 '새 메일 쓰기'로 첫 메일을 보내 보세요."}</Empty> :
        <div className="split">
          <Card kind="flat" guide="mail-list"><div className="list" role="list">{mails.map((m) => (
            <button key={m.id} aria-current={sel?.id === m.id} onClick={() => setSel(m)}>
              <div className="row"><b className="trunc grow">{box === "in" ? m.from.name : peopleOf(m)}</b><span className="small faint">{ago(m.ts)}</span></div>
              <div className="trunc small">{m.subject}</div></button>))}</div></Card>
          {sel && <Card guide="mail-reader"><div className="stack">
            <h2 style={{ marginBottom: 0 }}>{sel.subject}</h2>
            <div className="row wrap small muted"><span>{sel.from.name === sel.from.email ? sel.from.name : `${sel.from.name} <${sel.from.email}>`}</span>{sel.external && <Badge kind="warn">외부 발신</Badge>}
              {box === "sent" && <span>→ {peopleOf(sel)}</span>}</div>
            <p style={{ whiteSpace: "pre-wrap" }}>{sel.body}</p>
            {box === "in" && <div><button className="btn sm" onClick={() => replyTo(sel)}>답장</button></div>}</div></Card>}
        </div>}
    </>
  );
}
