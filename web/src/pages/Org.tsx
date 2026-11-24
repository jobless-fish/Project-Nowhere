import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { world } from "../api";
import type { OrgData, Person, PersonDetail, Session } from "../types";
import { Avatar, Badge, Card, Empty, PageHead, Skeletons } from "../ui";

const rank = (p: Pick<Person, "position" | "grade">) => (p.position === "팀원" ? p.grade : p.position);
const SITE = (l: string) => l.replace("서울 ", "").replace("경기 ", "");

export default function Org({ s }: { s: Session }) {
  const [org, setOrg] = useState<OrgData | null>(null), [err, setErr] = useState(false);
  const [me, setMe] = useState<PersonDetail | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [site, setSite] = useState("");
  const [unit, setUnit] = useState<{ dept: string; unit: string } | null>(null);
  const [members, setMembers] = useState<Person[] | null>(null);
  const [sel, setSel] = useState<PersonDetail | null>(null);
  const [q, setQ] = useState(""), [hits, setHits] = useState<Person[]>([]), [hi, setHi] = useState(0), [showHits, setShowHits] = useState(false);
  const lid = useId(), box = useRef<HTMLDivElement>(null), card = useRef<HTMLDivElement>(null);

  useEffect(() => { world.get<OrgData>("/directory/org", s).then(setOrg).catch(() => setErr(true)); }, [s]);
  useEffect(() => { world.get<PersonDetail>(`/directory/people/${s.user.id}`, s).then((p) => { setMe(p); setOpen((o) => new Set(o).add(p.dept)); }).catch(() => {}); }, [s]);
  useEffect(() => {
    if (!q.trim()) { setHits([]); return; }
    const t = setTimeout(() => world.get<{ items: Person[] }>(`/directory/people?q=${encodeURIComponent(q)}&limit=8`, s).then((r) => { setHits(r.items); setHi(0); }).catch(() => setHits([])), 150);
    return () => clearTimeout(t);
  }, [q, s]);
  useEffect(() => { const f = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setShowHits(false); }; document.addEventListener("mousedown", f); return () => document.removeEventListener("mousedown", f); }, []);
  useEffect(() => {
    if (!unit) { setMembers(null); return; }
    const qs = new URLSearchParams({ limit: "100", dept: unit.dept, unit: unit.unit });
    world.get<{ items: Person[] }>(`/directory/people?${qs}`, s).then((r) => setMembers(r.items)).catch(() => setMembers([]));
  }, [unit, s]);

  const show = useCallback((id: string) => world.get<PersonDetail>(`/directory/people/${id}`, s).then((p) => {
    setSel(p); setOpen((o) => new Set(o).add(p.dept)); setUnit({ dept: p.dept, unit: p.unit });
    window.setTimeout(() => card.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }), 50);
  }).catch(() => {}), [s]);
  useEffect(() => { const id = new URLSearchParams(location.hash.split("?")[1] ?? "").get("person"); if (id) { void show(id); history.replaceState(null, "", "#/org"); } }, [show]);
  const toggle = (d: string) => setOpen((o) => { const n = new Set(o); if (n.has(d)) n.delete(d); else n.add(d); return n; });
  const pick = (p: Person) => { setQ(""); setShowHits(false); void show(p.id); };
  const keys = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setShowHits(true); setHi((h) => Math.min(h + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)); }
    else if (e.key === "Enter" && hits[hi]) { e.preventDefault(); pick(hits[hi]); }
    else if (e.key === "Escape") { setShowHits(false); setQ(""); }
  };
  const depts = useMemo(() => org?.departments.filter((d) => !site || d.location.includes(site)) ?? [], [org, site]);

  if (err) return <><PageHead title="조직도" /><Empty>조직 정보를 불러오지 못했어요.</Empty></>;
  if (!org) return <><PageHead title="조직도" /><Skeletons /></>;
  const sites = org.company.sites.map(SITE);
  const mine = (dept: string, u?: string) => !!me && me.dept === dept && (!u || me.unit === u);
  const chainIds = new Set(sel ? [sel.id, ...sel.chain_of_command.map((c) => c.id)] : []);
  const person = (p: Person, extra?: React.ReactNode) => (
    <button key={p.id} aria-current={sel?.id === p.id} onClick={() => show(p.id)}>
      <span className="row"><Avatar name={p.name} /><span className="grow trunc"><b>{p.name}</b> <span className="muted small">{rank(p)}</span><span className="small muted trunc" style={{ display: "block" }}>{p.job_title}</span></span>{extra}</span></button>);

  return (
    <>
      <PageHead title="조직도" sub={`${org.company.name} · 임직원 ${org.headcount}명 · 본부 ${org.departments.length}개. 모든 인물은 가상이에요.`} />
      <div className="orgbar">
        <div className="picker grow" ref={box} data-guide="org-search">
          <label className="small muted" htmlFor="q">사람 찾기 — 이름·직무·팀·이메일</label>
          <input id="q" value={q} role="combobox" aria-expanded={showHits && hits.length > 0} aria-controls={lid} aria-autocomplete="list" autoComplete="off"
            onChange={(e) => { setQ(e.target.value); setShowHits(true); }} onFocus={() => setShowHits(true)} onKeyDown={keys} placeholder="예) 백엔드, 보상심사, 김" />
          {showHits && q.trim() && (
            <ul className="picker-list" id={lid} role="listbox">
              {hits.length === 0 ? <li className="small muted" style={{ padding: 12 }}>찾는 사람이 없어요.</li> : hits.map((p, i) => (
                <li key={p.id} role="option" aria-selected={i === hi}><button type="button" className={i === hi ? "on" : ""} onMouseEnter={() => setHi(i)} onClick={() => pick(p)}>
                  <Avatar name={p.name} /><span className="grow"><b>{p.name}</b> <span className="muted small">{rank(p)}</span><div className="small muted">{p.dept} · {p.unit}</div></span></button></li>))}
            </ul>)}
        </div>
        <div className="seg-filter" role="group" aria-label="근무지">
          {["", ...sites].map((x) => <button key={x} className={site === x ? "on" : ""} aria-pressed={site === x} onClick={() => setSite(x)}>{x || "전체"}</button>)}
        </div>
      </div>

      <div className="split" style={{ gridTemplateColumns: "minmax(0,5fr) minmax(0,4fr)", alignItems: "start" }}>
        <div className="stack" style={{ gap: 10 }} data-guide="org-depts">
          <Card kind="flat"><button className="orghead" onClick={() => show(org.ceo.id)}><Avatar name={org.ceo.name} /><span className="grow"><b>{org.ceo.name}</b> <span className="muted">대표이사</span><span className="small muted" style={{ display: "block" }}>직속 {org.departments.length}개 본부·실</span></span></button></Card>
          {depts.map((d) => {
            const isOpen = open.has(d.name);
            return (
              <Card key={d.key} kind="flat"><div className="orgdept">
                <button className="orghead" aria-expanded={isOpen} onClick={() => toggle(d.name)}>
                  <span className="caret" aria-hidden="true">{isOpen ? "▾" : "▸"}</span>
                  <span className="grow"><b>{d.name}</b> {mine(d.name) && <Badge kind="accent">내 소속</Badge>}<span className="small muted" style={{ display: "block" }}>{rank(d.head)} {d.head.name}</span></span>
                  <Badge>{d.headcount}명</Badge><Badge kind="accent">{SITE(d.location)}</Badge></button>
                {isOpen && <div className="orgunits">
                  <button className={chainIds.has(d.head.id) ? "chain" : ""} onClick={() => show(d.head.id)}><span className="grow"><b>{d.head.name}</b> <span className="small muted">{rank(d.head)} · 본부장</span></span></button>
                  {d.units.map((u) => (
                    <button key={u.name} aria-current={unit?.unit === u.name && unit.dept === d.name} onClick={() => { setUnit({ dept: d.name, unit: u.name }); setSel(null); }}>
                      <span className="grow"><b>{u.name}</b> {mine(d.name, u.name) && <Badge kind="accent">내 팀</Badge>}{u.lead && <span className="small muted" style={{ display: "block" }}>팀장 {u.lead.name}</span>}</span>
                      <span className="small muted">{u.headcount}명</span></button>))}
                </div>}
              </div></Card>);
          })}
          {depts.length === 0 && <Empty>이 근무지의 본부가 없어요.</Empty>}
        </div>

        <div className="stack orgside" style={{ gap: 12 }} ref={card}>
          {sel && (
            <Card guide="org-person"><div className="stack">
              <nav className="crumbs small" aria-label="보고 라인">{[...sel.chain_of_command].reverse().map((c) => <span key={c.id}><button onClick={() => show(c.id)}>{c.name}</button> › </span>)}<b>{sel.name}</b></nav>
              <div className="row"><Avatar name={sel.name} /><div className="grow"><b style={{ fontSize: 18 }}>{sel.name}</b> <span className="muted">{rank(sel)}</span><div className="small muted">{sel.job_title}</div></div>{sel.id === s.user.id && <Badge kind="accent">나</Badge>}</div>
              <dl className="facts"><dt>소속</dt><dd>{sel.dept} · {sel.unit}</dd><dt>근무지</dt><dd>{sel.location}</dd><dt>이메일</dt><dd>{sel.email}</dd><dt>내선</dt><dd>{sel.ext}</dd>
                <dt>입사</dt><dd>{sel.hire_date.slice(0, 7)} · {sel.employment}{sel.status !== "재직" ? ` · ${sel.status}` : ""}</dd></dl>
              {sel.id !== s.user.id && <div className="row wrap"><a className="btn primary sm" href={`#/mail?to=${sel.id}`}>메일 쓰기</a><a className="btn sm" href={`#/chat?dm=${sel.id}`}>메시지 보내기</a></div>}
              {sel.direct_reports.length > 0 && <div><div className="mono small faint" style={{ marginBottom: 6 }}>↳ 직속 {sel.direct_reports.length}명</div>
                <div className="row wrap" style={{ gap: 6 }}>{sel.direct_reports.slice(0, 16).map((r) => <button key={r.id} className="chip pbtn" onClick={() => show(r.id)}>{r.name}</button>)}{sel.direct_reports.length > 16 && <span className="small muted">외 {sel.direct_reports.length - 16}명</span>}</div></div>}
            </div></Card>)}
          {unit && (
            <Card guide="org-result"><h2 style={{ marginBottom: 8 }}>{unit.unit} <span className="small muted">{members ? `${members.length}명` : ""}</span></h2>
              <p className="small muted" style={{ marginBottom: 8 }}>{unit.dept}</p>
              {!members ? <Skeletons n={2} /> : members.length === 0 ? <Empty>구성원이 없어요.</Empty> : <div className="list">{members.map((p) => person(p, p.position === "팀장" ? <Badge>팀장</Badge> : undefined))}</div>}
            </Card>)}
          {!sel && !unit && <Card kind="flat"><p className="muted small">왼쪽에서 본부를 열고 팀을 고르거나, 위에서 이름을 검색해 보세요. 사람을 누르면 보고 라인과 연락 버튼이 나와요.{me && <> 내 소속은 <b>{me.dept} · {me.unit}</b>이에요.</>}</p></Card>}
        </div>
      </div>
    </>
  );
}
