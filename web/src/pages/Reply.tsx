import { useState } from "react";
import { api } from "../api";
import type { Action } from "../types";
import { Badge } from "../ui";

type Props = { uid: string; action?: Action; busy: boolean; onPropose: () => void; onChanged: () => void };

export default function Reply({ uid, action, busy, onPropose, onChanged }: Props) {
  const [subject, setSubject] = useState<string | null>(null);
  const [body, setBody] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [err, setErr] = useState("");
  if (!action) return <div><button className="btn sm" onClick={onPropose} disabled={busy} aria-busy={busy || undefined}>답장 초안 만들기</button></div>;
  if (action.status === "sent") return <p className="small"><Badge kind="ok">발송됨</Badge> {action.to_name}님께 {action.edited ? "수정한 내용으로" : "초안 그대로"} 보냈습니다.</p>;
  if (action.status === "rejected") return <p className="small muted">초안을 반려했습니다.</p>;
  if (action.status === "failed") return <p className="small" role="alert"><Badge kind="urgent">발송 실패</Badge> {action.note}</p>;
  if (action.status === "blocked") return <div className="banner" role="status"><span>{action.note}</span></div>;

  const decide = async (approve: boolean) => {
    setErr("");
    try {
      await api.post(`/assistant/actions/${action.id}/decision`, { user_id: uid, approve, subject, body, confirm_external: ok });
      onChanged();
    } catch (e) { setErr(e instanceof Error && e.message.includes("external") ? "외부 수신자 확인에 체크해 주세요." : "처리하지 못했습니다. 다시 시도해 주세요."); }
  };
  return (
    <div className="stack" style={{ gap: 8, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
      <div className="row wrap small"><b>받는 사람</b><span>{action.to_name}</span>{action.external ? <Badge kind="warn">외부</Badge> : <Badge>사내</Badge>}
        <span className="faint">AI 초안입니다. 보내기 전에 꼭 확인하세요.</span></div>
      <label className="small muted" htmlFor={`s${action.id}`}>제목</label>
      <input id={`s${action.id}`} value={subject ?? action.draft_subject} onChange={(e) => setSubject(e.target.value)} />
      <label className="small muted" htmlFor={`b${action.id}`}>본문</label>
      <textarea id={`b${action.id}`} rows={5} value={body ?? action.draft_body} onChange={(e) => setBody(e.target.value)} />
      {action.external && <label className="row small" style={{ gap: 8 }}><input type="checkbox" style={{ width: 18 }} checked={ok} onChange={(e) => setOk(e.target.checked)} />
        외부 수신자에게 발송됨을 확인했습니다</label>}
      {err && <p className="small" role="alert" style={{ color: "var(--danger)" }}>{err}</p>}
      <div className="row"><button className="btn primary sm" onClick={() => decide(true)}>승인하고 보내기</button>
        <button className="btn quiet sm" onClick={() => decide(false)}>반려</button></div>
    </div>
  );
}
