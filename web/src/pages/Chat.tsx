import { useEffect, useState } from "react";
import { world } from "../api";
import type { Channel, ChatMsg, Session } from "../types";
import { Avatar, Card, Empty, PageHead, Skeletons, ago } from "../ui";

export default function Chat({ s }: { s: Session }) {
  const [chs, setChs] = useState<Channel[] | null>(null);
  const [cur, setCur] = useState<Channel | null>(null);
  const [msgs, setMsgs] = useState<ChatMsg[] | null>(null);
  useEffect(() => { world.get<Channel[]>("/chat/channels", s).then((c) => { setChs(c); setCur(c[0] ?? null); }).catch(() => setChs([])); }, [s]);
  useEffect(() => {
    if (!cur) return;
    setMsgs(null);
    world.get<{ items: ChatMsg[] }>(`/chat/channels/${cur.id}/messages?hours=72&limit=100`, s).then((r) => setMsgs(r.items)).catch(() => setMsgs([]));
  }, [cur, s]);
  return (
    <>
      <PageHead title="메신저" sub="참여 중인 채널만 표시됩니다." />
      {!chs ? <Skeletons /> : chs.length === 0 ? <Empty>참여 중인 채널이 없습니다.</Empty> :
        <div className="split">
          <Card kind="flat" guide="chat-channels"><div className="list">{chs.map((c) => (
            <button key={c.id} aria-current={cur?.id === c.id} onClick={() => setCur(c)}># {c.name}{c.private && <span className="small faint"> · 비공개</span>}</button>))}</div></Card>
          <Card guide="chat-messages">{!msgs ? <Skeletons n={2} /> : msgs.length === 0 ? <Empty>최근 메시지가 없습니다.</Empty> :
            <div className="stack" style={{ gap: 16 }}>{msgs.map((m) => (
              <div key={m.id} className="row" style={{ alignItems: "flex-start" }}><Avatar name={m.author.name} />
                <div><b>{m.author.name}</b> <span className="small faint">{ago(m.ts)}</span><p>{m.text}</p></div></div>))}</div>}</Card>
        </div>}
    </>
  );
}
