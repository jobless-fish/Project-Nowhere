import { useEffect, useState } from "react";
import { world } from "../api";
import type { OrgData, Person, PersonDetail, Session } from "../types";
import { Avatar, Badge, Card, Empty, PageHead, Skeletons } from "../ui";

const who = (p: Person) => `${p.name} ${p.position === "팀원" ? p.grade : p.position}`;

export default function Org({ s }: { s: Session }) {
  const [org, setOrg] = useState<OrgData | null>(null);
  const [q, setQ] = useState("");
  const [unit, setUnit] = useState<{ dept: string; unit: string } | null>(null);
  const [list, setList] = useState<Person[] | null>(null);
  const [total, setTotal] = useState(0);
  const [sel, setSel] = useState<PersonDetail | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => { world.get<OrgData>("/directory/org", s).then(setOrg).catch(() => setErr(true)); }, [s]);
  useEffect(() => {
    if (!q && !unit) { setList(null); return; }
    const t = setTimeout(() => {
      const qs = new URLSearchParams({ limit: "100" });
      if (q) qs.set("q", q);
      if (unit) { qs.set("dept", unit.dept); qs.set("unit", unit.unit); }
      world.get<{ items: Person[]; total: number }>(`/directory/people?${qs}`, s).then((r) => { setList(r.items); setTotal(r.total); }).catch(() => setList([]));
    }, 200);
    return () => clearTimeout(t);
  }, [q, unit, s]);
  const open = (id: string) => world.get<PersonDetail>(`/directory/people/${id}`, s).then(setSel).catch(() => {});

  if (err) return <><PageHead title="조직도" /><Empty>조직 정보를 불러오지 못했어요.</Empty></>;
  if (!org) return <><PageHead title="조직도" /><Skeletons /></>;
  return (
    <>
      <PageHead title="조직도" sub={`${org.company.name} · 임직원 ${org.headcount}명 · 본부 ${org.departments.length}개 · 근무지 ${org.company.sites.length}곳 (${org.company.sites.join(", ")}). 모든 인물은 가상이에요.`} />
      <div className="split" style={{ gridTemplateColumns: "minmax(0,5fr) minmax(0,4fr)" }}>
        <div className="stack" style={{ gap: 12 }}>
          <label className="small muted" htmlFor="q">이름·직무·팀·이메일로 찾기</label>
          <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="예) 백엔드, 보상심사, 김" />
          <Card kind="flat"><div className="row" style={{ gap: 12 }}><Avatar name={org.ceo.name} /><div><b>{org.ceo.name}</b> <span className="muted">대표이사</span><div className="small muted">직속 {org.departments.length}개 본부·실</div></div></div></Card>
          {org.departments.map((d) => (
            <details key={d.key} className="card flat" style={{ padding: 0 }}>
              <summary style={{ padding: 16, cursor: "pointer", minHeight: 44, listStyle: "none" }}>
                <div className="row wrap"><b className="grow">{d.name}</b><Badge>{d.headcount}명</Badge><Badge kind="accent">{d.location.replace("서울 ", "")}</Badge></div>
                <div className="small muted">{who(d.head)} · {d.head.job_title}</div>
              </summary>
              <div className="list" style={{ borderTop: "1px solid var(--border)" }}>
                {d.units.map((u) => (
                  <button key={u.name} aria-current={unit?.unit === u.name} onClick={() => { setQ(""); setUnit({ dept: d.name, unit: u.name }); }}>
                    <div className="row"><b className="grow">{u.name}</b><span className="small muted">{u.headcount}명</span></div>
                    {u.lead && <div className="small muted">팀장 {u.lead.name}</div>}
                  </button>
                ))}
              </div>
            </details>
          ))}
        </div>
        <div className="stack" style={{ gap: 12 }}>
          {list && (
            <Card><h2 style={{ marginBottom: 8 }}>{unit && !q ? unit.unit : "검색 결과"} <span className="small muted">({total}명)</span></h2>
              {list.length === 0 ? <Empty>찾는 사람이 없어요.</Empty> : <div className="list">{list.map((p) => (
                <button key={p.id} aria-current={sel?.id === p.id} onClick={() => open(p.id)}>
                  <div className="row"><b className="grow">{p.name}</b><span className="small muted">{p.position === "팀원" ? p.grade : p.position}</span></div>
                  <div className="small muted trunc">{p.unit} · {p.job_title}</div></button>))}</div>}
            </Card>)}
          {!list && !sel && <Card kind="flat"><p className="muted small">왼쪽에서 팀을 고르거나 검색해 보세요. 사람을 누르면 보고 라인이 나와요.</p></Card>}
          {sel && (
            <Card><div className="stack">
              <div className="row"><Avatar name={sel.name} /><div className="grow"><b>{sel.name}</b> <span className="muted">{sel.position === "팀원" ? sel.grade : sel.position}</span><div className="small muted">{sel.job_title}</div></div></div>
              <div className="small muted">{sel.dept} · {sel.unit}<br />{sel.location} · 내선 {sel.ext}<br />{sel.email}<br />입사 {sel.hire_date.slice(0, 7)} · {sel.employment}{sel.status !== "재직" ? ` · ${sel.status}` : ""}</div>
              {sel.chain_of_command.length > 0 && <div><div className="mono small faint">↳ 보고 라인</div>{sel.chain_of_command.map((c) => <div key={c.id} className="small">{who(c)} <span className="muted">· {c.job_title}</span></div>)}</div>}
              {sel.direct_reports.length > 0 && <div><div className="mono small faint">↳ 직속 {sel.direct_reports.length}명</div><div className="row wrap" style={{ gap: 6 }}>{sel.direct_reports.slice(0, 12).map((r) => <span key={r.id} className="chip">{r.name}</span>)}</div></div>}
            </div></Card>)}
        </div>
      </div>
    </>
  );
}
