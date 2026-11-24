import { useCallback, useEffect, useState } from "react";
import { world } from "../api";
import type { CalEvent, HistoryItem, Overview, Party, Session, Term, WikiDoc, WikiRow, YearDetail, YearRec } from "../types";
import { Badge, Card, Empty, Failed, PageHead, Skeletons } from "../ui";

const nf = new Intl.NumberFormat("ko-KR");
const KIND_KO: Record<string, string> = { company: "회사", funding: "투자", product: "제품", customer: "고객", site: "사무실", org: "조직" };
const EV_KO: Record<string, string> = { holiday: "휴일", company: "행사", deadline: "마감", outage: "공지" };
const dow = (iso: string) => ["일", "월", "화", "수", "목", "금", "토"][new Date(iso + "T00:00:00").getDay()];

function useGet<T>(s: Session, path: string) {
  const [d, setD] = useState<T | null>(null), [bad, setBad] = useState(false);
  const load = useCallback(() => { setBad(false); world.get<T>(path, s).then(setD).catch(() => setBad(true)); }, [s, path]);
  useEffect(() => { load(); }, [load]);
  return { d, bad, load };
}

function Home({ s }: { s: Session }) {
  const o = useGet<Overview>(s, "/company/overview"), h = useGet<{ items: HistoryItem[] }>(s, "/company/history");
  if (o.bad || h.bad) return <Failed what="회사 정보" onRetry={() => { o.load(); h.load(); }} />;
  if (!o.d || !h.d) return <Skeletons />;
  const { stats, products, next_events } = o.d;
  return (
    <div className="stack" style={{ gap: 20 }}>
      <Card><div className="stack">
        <p>{o.d.company.name}은 <b>보험사·GA</b>를 위한 업무 자동화 서비스를 만드는 {o.d.company.stage} 스타트업이에요. {o.d.company.founded}년에 설립했고 본사는 {o.d.company.hq}에 있어요.</p>
        <div className="row wrap small muted"><span>임직원 {nf.format(stats.headcount)}명</span><span>·</span><span>고객사 {stats.customers}곳(운영 중 {stats.running})</span><span>·</span><span>연 계약 규모 합계 {stats.annual_eok}억원</span><span>·</span><span>거래처 {stats.vendors}곳</span></div>
        {stats.attention.length > 0 && <p className="small"><Badge kind="warn">주의</Badge> 갱신 협의 중 확인이 필요한 고객사: {stats.attention.join(", ")}</p>}
      </div></Card>
      <section><h2>제품</h2><div className="stack">{products.map((p) => <Card key={p.id} kind="flat"><div className="row wrap"><b>{p.name}</b><Badge kind={p.status === "운영" ? "ok" : "accent"}>{p.status}</Badge><span className="small muted grow">{p.what}</span><span className="small faint">{p.since} · {p.owner_dept}</span></div></Card>)}</div></section>
      {next_events.length > 0 && <section><h2>다가오는 일정</h2><Card kind="flat"><div className="stack" style={{ gap: 8 }}>{next_events.slice(0, 5).map((e) => <div key={e.date + e.title} className="row"><span className="mono small faint" style={{ width: 92 }}>{e.date.slice(5)} ({dow(e.date)})</span><Badge>{EV_KO[e.kind] ?? e.kind}</Badge><span className="grow">{e.title}</span></div>)}</div></Card></section>}
      <section><h2>걸어온 길</h2><ol className="timeline">{h.d.items.map((x) => <li key={x.month + x.title}><span className="mono small faint">{x.month}</span><div><b>{x.title}</b> <Badge>{KIND_KO[x.kind] ?? x.kind}</Badge><p className="small muted">{x.detail}</p></div></li>)}</ol></section>
    </div>
  );
}

function Parties({ s, onOwner }: { s: Session; onOwner: (id: string) => void }) {
  const [kind, setKind] = useState(""), [q, setQ] = useState(""), [sel, setSel] = useState<string | null>(null);
  const r = useGet<{ items: Party[] }>(s, `/company/customers?kind=${encodeURIComponent(kind)}&q=${encodeURIComponent(q)}`);
  const p = r.d?.items.find((x) => x.id === sel) ?? null;
  return (
    <div className="stack">
      <div className="row wrap">
        <div className="seg-filter" role="group" aria-label="종류">{["", "고객사", "거래처", "투자사"].map((k) => <button key={k} className={kind === k ? "on" : ""} aria-pressed={kind === k} onClick={() => { setKind(k); setSel(null); }}>{k || "전체"}</button>)}</div>
        <div className="grow"><label className="sr" htmlFor="pq">검색</label><input id="pq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="회사·제품·담당자 이름으로 찾기" /></div>
      </div>
      {r.bad ? <Failed what="고객·거래처" onRetry={r.load} /> : !r.d ? <Skeletons /> : r.d.items.length === 0 ? <Empty>찾는 곳이 없어요.</Empty> :
        <div className="split"><Card kind="flat"><div className="list">{r.d.items.map((x) => <button key={x.id} aria-current={sel === x.id} onClick={() => setSel(x.id)}>
          <div className="row"><b className="grow trunc">{x.name}</b>{x.health === "주의" && <Badge kind="warn">주의</Badge>}<span className="small faint">{x.kind}</span></div><div className="small muted trunc">{x.what} · {x.stage}</div></button>)}</div></Card>
          {p ? <Card><div className="stack">
            <div className="row wrap"><h2 style={{ marginBottom: 0 }}>{p.name}</h2><Badge>{p.kind}</Badge><Badge kind={p.health === "주의" ? "warn" : "ok"}>{p.health}</Badge></div>
            <dl className="facts"><dt>구분</dt><dd>{p.what}</dd><dt>단계</dt><dd>{p.stage}</dd>{p.product && <><dt>제품</dt><dd>{p.product}</dd></>}{p.category && <><dt>분야</dt><dd>{p.category}</dd></>}
              <dt>관계 시작</dt><dd>{p.since}</dd>{p.renewal && <><dt>갱신</dt><dd>{p.renewal}</dd></>}{!!p.annual_eok && <><dt>연 규모</dt><dd>{p.annual_eok}억원</dd></>}
              <dt>담당자</dt><dd>{p.contact.name} · {p.contact.email}</dd></dl>
            {p.owner && <div className="row wrap"><span className="small muted">우리 쪽 담당: <b>{p.owner.name}</b> ({p.owner.unit})</span><button className="btn sm" onClick={() => onOwner(p.owner!.id)}>조직도에서 보기</button><a className="btn sm" href={`#/mail?to=${p.owner.id}`}>메일 쓰기</a></div>}
          </div></Card> : <Card kind="flat"><p className="muted small">왼쪽에서 한 곳을 고르면 계약 단계와 우리 쪽 담당자가 보여요. 메일함에 오는 외부 발신자는 모두 여기 있는 곳들이에요.</p></Card>}</div>}
    </div>
  );
}

function Wiki({ s }: { s: Session }) {
  const [q, setQ] = useState(""), [slug, setSlug] = useState("expense");
  const l = useGet<{ items: WikiRow[] }>(s, `/company/wiki?q=${encodeURIComponent(q)}`), d = useGet<WikiDoc>(s, `/company/wiki/${slug}`);
  return (
    <div className="stack">
      <div><label className="small muted" htmlFor="wq">규정 찾기 — 예) 택시, 피싱, 휴가</label><input id="wq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="찾을 말을 입력하세요" /></div>
      <div className="split">
        <Card kind="flat"><div className="list">{l.bad ? <Failed what="위키" onRetry={l.load} /> : !l.d ? <Skeletons n={3} /> : l.d.items.length === 0 ? <Empty>맞는 문서가 없어요.</Empty> : l.d.items.map((x) =>
          <button key={x.slug} aria-current={slug === x.slug} onClick={() => setSlug(x.slug)}><b>{x.title}</b><div className="small muted trunc">{x.snippet ? `…${x.snippet}…` : `${x.owner} · ${x.updated} 수정`}</div></button>)}</div></Card>
        {d.d && <Card><div className="stack"><h2 style={{ marginBottom: 0 }}>{d.d.title}</h2><div className="row wrap small muted"><span>{d.d.owner}</span><span>·</span><span>{d.d.updated} 수정</span>{d.d.tags.map((t) => <span key={t} className="chip">{t}</span>)}</div>
          <p style={{ whiteSpace: "pre-wrap" }}>{d.d.body}</p></div></Card>}
      </div>
    </div>
  );
}

function Glossary({ s }: { s: Session }) {
  const [q, setQ] = useState("");
  const r = useGet<{ items: Term[] }>(s, `/company/glossary?q=${encodeURIComponent(q)}`);
  return (
    <div className="stack">
      <div><label className="small muted" htmlFor="gq">낯선 말이 있나요?</label><input id="gq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="예) 언더, 온콜, P1" /></div>
      {r.bad ? <Failed what="용어집" onRetry={r.load} /> : !r.d ? <Skeletons /> : r.d.items.length === 0 ? <Empty>찾는 말이 없어요.</Empty> :
        <Card kind="flat"><dl className="gloss">{r.d.items.map((t) => <div key={t.term}><dt><b>{t.term}</b> <Badge>{t.group}</Badge></dt><dd>{t.meaning}</dd></div>)}</dl></Card>}
    </div>
  );
}

function Years({ s }: { s: Session }) {
  const list = useGet<{ items: YearRec[] }>(s, "/company/years");
  const [year, setYear] = useState(2026);
  const d = useGet<YearDetail>(s, `/company/years/${year}`);
  if (list.bad) return <Failed what="연도별 기록" onRetry={list.load} />;
  const max = Math.max(...(list.d?.items.map((y) => y.headcount) ?? [1]));
  return (
    <div className="stack" style={{ gap: 20 }}>
      <Card kind="flat"><div className="stack"><h2 style={{ marginBottom: 0 }}>해마다 이만큼 커졌어요</h2>
        <p className="small muted">막대는 그해 말 임직원 수예요. 입사일은 로스터에서, 이미 퇴사한 사람은 일정한 비율로 보정해서 계산했어요.</p>
        <div className="bars" role="img" aria-label="연도별 임직원 수">{list.d?.items.map((y) => <button key={y.year} className={y.year === year ? "on" : ""} onClick={() => setYear(y.year)} aria-pressed={y.year === year}>
          <span className="bar" style={{ height: `${Math.max(8, (y.headcount / max) * 100)}%` }} /><b>{y.headcount}</b><span className="small muted">{y.year}</span></button>)}</div></div></Card>
      {d.bad ? <Failed what={`${year}년 기록`} onRetry={d.load} /> : !d.d ? <Skeletons /> : <>
        <Card><div className="stack">
          <h2 style={{ marginBottom: 0 }}>{year}년{d.d.in_progress && <span className="small muted"> · 진행 중(11월 기준)</span>}</h2>
          <div className="row wrap small"><span>연말 임직원 <b>{d.d.headcount}명</b> (이 해 입사 {d.d.hired}명)</span><span>·</span><span>고객사 <b>{d.d.customers}곳</b></span><span>·</span><span>매출 <b>{d.d.revenue_eok}억원</b></span><span>·</span><span>장애 P1 {d.d.p1} · P2 {d.d.p2}</span></div>
          <table className="tbl"><thead><tr><th>분기</th><th>인원</th><th>고객사</th><th>매출(억)</th><th>P1</th><th>P2</th></tr></thead><tbody>{d.d.quarters.map((q) => <tr key={q.label}><td>{q.label}{q.in_progress ? " (진행 중)" : ""}</td><td>{q.headcount}</td><td>{q.customers}</td><td>{q.revenue_eok}</td><td>{q.p1}</td><td>{q.p2}</td></tr>)}</tbody></table>
          {d.d.hires.length > 0 && <p className="small muted">입사: {d.d.hires.map((h) => `${h.dept} ${h.count}명`).join(" · ")}</p>}
        </div></Card>
        <section><h2>이 해의 일</h2><ol className="timeline">{d.d.events.map((x) => <li key={x.month + x.title}><span className="mono small faint">{x.month}</span><div><b>{x.title}</b> <Badge>{KIND_KO[x.kind] ?? x.kind}</Badge><p className="small muted">{x.detail}</p></div></li>)}</ol></section>
        {d.d.postmortems.length > 0 && <section><h2>장애와 사후 분석</h2><div className="stack">{d.d.postmortems.map((p) => <Card key={p.date} kind="flat"><div className="stack" style={{ gap: 4 }}>
          <div className="row wrap"><Badge kind={p.severity === "P1" ? "urgent" : "warn"}>{p.severity}</Badge><b>{p.title}</b><span className="small faint">{p.date} · {p.unit}</span></div>
          <p className="small"><b>영향</b> {p.impact}</p><p className="small"><b>원인</b> {p.cause}</p><p className="small"><b>재발 방지</b> {p.fix}</p></div></Card>)}</div></section>}
        {d.d.townhalls.length > 0 && <section><h2>타운홀 기록</h2><Card kind="flat"><div className="stack" style={{ gap: 10 }}>{d.d.townhalls.map((t) => <p key={t.label} className="small"><b>{t.label}</b> {t.text}</p>)}</div></Card></section>}
      </>}
    </div>
  );
}

function Calendar({ s }: { s: Session }) {
  const [year, setYear] = useState(2026);
  const r = useGet<{ today: string; items: CalEvent[] }>(s, `/company/calendar?year=${year}`);
  return (
    <div className="stack">
      <div className="row wrap"><button className="btn sm" onClick={() => setYear(year - 1)} disabled={year <= 2019} aria-label="이전 해">‹</button><b style={{ fontSize: 18 }}>{year}년</b><button className="btn sm" onClick={() => setYear(year + 1)} disabled={year >= 2027} aria-label="다음 해">›</button>
        <span className="small muted">공휴일(주요 날짜)과 사내 정례 행사예요. 주말에는 행사를 잡지 않아요.</span></div>
      {r.bad ? <Failed what="달력" onRetry={r.load} /> : !r.d ? <Skeletons /> : r.d.items.length === 0 ? <Empty>일정이 없어요.</Empty> :
        <Card kind="flat"><div className="stack" style={{ gap: 10 }}>{r.d.items.map((e) => <div key={e.date + e.title} className="row" style={{ opacity: e.date < r.d!.today ? .55 : 1 }}>
          <span className="mono small faint" style={{ width: 120 }}>{e.date} ({dow(e.date)})</span><Badge kind={e.kind === "deadline" ? "warn" : e.kind === "holiday" ? "ok" : ""}>{EV_KO[e.kind] ?? e.kind}</Badge><span className="grow">{e.title}</span></div>)}</div></Card>}
    </div>
  );
}

export default function Company({ s }: { s: Session }) {
  const [tab, setTab] = useState("home");
  const T = [["home", "개요·연혁"], ["parties", "고객·거래처"], ["wiki", "위키"], ["years", "연도별 기록"], ["gloss", "용어집"], ["cal", "달력"]];
  return (
    <>
      <PageHead title="회사" sub="이미 운영 중인 회사의 제품, 고객, 규정, 달력이에요. 모두 가상이고, 서로 일관되게 맞물려 있어요." />
      <div className="tabs" role="tablist" data-guide="company-tabs">{T.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "home" ? <Home s={s} /> : tab === "parties" ? <Parties s={s} onOwner={(id) => { location.hash = `#/org?person=${id}`; }} /> : tab === "wiki" ? <Wiki s={s} /> : tab === "years" ? <Years s={s} /> : tab === "gloss" ? <Glossary s={s} /> : <Calendar s={s} />}
    </>
  );
}
