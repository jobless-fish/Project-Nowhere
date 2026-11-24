import { useEffect, useState } from "react";
import { api } from "../api";
import type { Digest, Session } from "../types";
import { Badge, Card, Empty, PageHead, Skeletons, SourceChip } from "../ui";

const LABEL: Record<string, string> = { chat: "메신저", slack: "메신저", notice: "공지", post: "게시판" };

export default function News({ s }: { s: Session }) {
  const [d, setD] = useState<Digest | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => { api.get<Digest>(`/assistant/news?user_id=${s.user.id}`).then(setD).catch(() => setErr(true)); }, [s.user.id]);
  return (
    <>
      <PageHead title="사내 소식" sub="메신저, 공지, 게시판의 새 소식을 요약했습니다. 내가 볼 수 있는 글만 포함됩니다." />
      {err ? <Empty>소식을 불러오지 못했습니다.</Empty> : !d ? <Skeletons /> : d.highlights.length === 0 ? <Empty>새 소식이 없습니다.</Empty> :
        <div className="stack">{d.highlights.map((h, i) => (
          <Card key={h.title} guide={h.category === "chat" ? (i === d.highlights.findIndex((x) => x.category === "chat") ? "news-chat" : undefined) : (i === d.highlights.findIndex((x) => x.category !== "chat") ? "news-official" : undefined)}><div className="stack" style={{ gap: 8 }}>
            <div className="row"><Badge kind="accent">{LABEL[h.category] ?? h.category}</Badge><b>{h.title}</b></div>
            <p>{h.summary}</p>
            <div className="row wrap" style={{ gap: 6 }}>{h.source_ids.map((id) => <SourceChip key={id} id={id} sources={d.sources} />)}</div>
          </div></Card>))}</div>}
    </>
  );
}
