import { useEffect, useState } from "react";
import { world } from "../api";
import type { Mail, Session } from "../types";
import { Badge, Card, Empty, PageHead, Skeletons, ago } from "../ui";

export default function MailPage({ s }: { s: Session }) {
  const [mails, setMails] = useState<Mail[] | null>(null);
  const [sel, setSel] = useState<Mail | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    world.get<{ items: Mail[] }>("/mail/inbox?hours=72&limit=100", s).then((r) => { setMails(r.items); setSel(r.items[0] ?? null); }).catch(() => setErr(true));
  }, [s]);
  return (
    <>
      <PageHead title="메일" sub="노웨어 사내 메일 서버의 받은편지함입니다." />
      {err ? <Empty>메일을 불러오지 못했습니다.</Empty> : !mails ? <Skeletons /> : mails.length === 0 ? <Empty>받은 메일이 없습니다.</Empty> :
        <div className="split">
          <Card kind="flat"><div className="list" role="list">{mails.map((m) => (
            <button key={m.id} aria-current={sel?.id === m.id} onClick={() => setSel(m)}>
              <div className="row"><b className="trunc grow">{m.from.name}</b><span className="small faint">{ago(m.ts)}</span></div>
              <div className="trunc small">{m.subject}</div></button>))}</div></Card>
          {sel && <Card><div className="stack">
            <h2 style={{ marginBottom: 0 }}>{sel.subject}</h2>
            <div className="row wrap small muted"><span>{sel.from.name === sel.from.email ? sel.from.name : `${sel.from.name} <${sel.from.email}>`}</span>{sel.external && <Badge kind="warn">외부 발신</Badge>}</div>
            <p style={{ whiteSpace: "pre-wrap" }}>{sel.body}</p></div></Card>}
        </div>}
    </>
  );
}
