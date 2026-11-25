import { useEffect, useRef, useState } from "react";
import { world } from "../api";
import type { Session } from "../types";
import { Badge, Card, Empty, PageHead } from "../ui";

type Hit = { id: string; kind: string; title: string; snippet: string; owner: string | null; ts: string };
type Doc = { id: string; title: string; body: string; kind: string; owner: string | null; ts: string };
const KIND: Record<string, string> = { doc: "문서", notice: "공지", post: "게시판", wiki: "위키" };

export default function Search({ s }: { s: Session }) {
  const [q, setQ] = useState(""), [kind, setKind] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null), [next, setNext] = useState<number | null>(null), [err, setErr] = useState("");
  const [open, setOpen] = useState<Doc | null>(null), [openErr, setOpenErr] = useState(false);
  const last = useRef(0);
  useEffect(() => {
    if (!q.trim()) { setHits(null); setNext(null); return; }
    const mine = ++last.current;                     // only the newest request may write (an older, slower answer must not overwrite it)
    const t = setTimeout(() => {
      world.get<{ items: Hit[]; next_offset: number | null }>(`/groupware/search?q=${encodeURIComponent(q.trim())}${kind ? `&kind=${kind}` : ""}`, s)
        .then((r) => { if (mine === last.current) { setHits(r.items); setNext(r.next_offset); setErr(""); } })
        .catch(() => { if (mine === last.current) { setHits([]); setErr("검색하지 못했어요. 잠시 뒤에 다시 해 주세요."); } });
    }, 200);
    return () => clearTimeout(t);
  }, [q, kind, s]);
  const more = () => next !== null && world.get<{ items: Hit[]; next_offset: number | null }>(`/groupware/search?q=${encodeURIComponent(q.trim())}${kind ? `&kind=${kind}` : ""}&offset=${next}`, s)
    .then((r) => { setHits((h) => [...(h ?? []), ...r.items]); setNext(r.next_offset); }).catch(() => setErr("더 불러오지 못했어요."));
  const show = async (id: string) => { setOpenErr(false); setOpen(null); try { setOpen(await world.get<Doc>(`/groupware/docs/${id}`, s)); } catch { setOpenErr(true); } };
  return (
    <>
      <PageHead title="문서 검색" sub="내가 열람할 수 있는 문서·공지·게시판·위키만 검색돼요. 권한이 없는 문서는 결과에 나타나지 않아요." />
      <div className="row wrap" style={{ gap: 8, marginBottom: 12 }}>
        <label className="sr-only" htmlFor="gw-q">검색어</label>
        <input id="gw-q" className="grow" data-guide="search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="예) 예산, 개인정보, 협상" />
        <label className="sr-only" htmlFor="gw-k">종류</label>
        <select id="gw-k" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">전체</option>{Object.entries(KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {err && <p className="small" role="alert">{err}</p>}
      {hits === null ? <Empty>검색어를 입력해 보세요.</Empty> : hits.length === 0 && !err ? <Empty>결과가 없어요. 다른 단어로 찾아보세요.</Empty> :
        <div className="stack" aria-live="polite">{hits.map((h) => (
          <Card key={h.id}><div className="stack" style={{ gap: 6 }}>
            <div className="row wrap"><Badge kind="accent">{KIND[h.kind] ?? h.kind}</Badge>
              <button className="btn quiet sm" onClick={() => show(h.id)}><b>{h.title}</b></button></div>
            <p className="small muted">{h.snippet}</p>
          </div></Card>))}
          {next !== null && <div><button className="btn sm" onClick={more}>더 보기</button></div>}</div>}
      {openErr && <p className="small" role="alert">열 수 없는 문서예요.</p>}
      {open && <Card guide="search-doc"><div className="stack" style={{ gap: 8 }}><div className="row wrap"><Badge>{KIND[open.kind] ?? open.kind}</Badge><b>{open.title}</b></div>
        <p style={{ whiteSpace: "pre-wrap" }}>{open.body}</p><div><button className="btn quiet sm" onClick={() => setOpen(null)}>닫기</button></div></div></Card>}
    </>
  );
}
