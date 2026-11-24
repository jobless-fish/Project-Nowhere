import { useEffect, useId, useRef, useState } from "react";
import { world } from "./api";
import type { Person, Session } from "./types";
import { Avatar } from "./ui";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export type Mini = { id: string; name: string; unit?: string };
export type Picked = { people: Mini[]; external: string[] };

/** Type-ahead recipient picker: colleagues from the directory (keyboard friendly) and, if allowed, outside e-mail addresses. */
export function PersonPicker({ s, value, onChange, placeholder = "이름이나 부서로 찾기", allowExternal = false, single = false, autoFocus = false, label }: {
  s: Session; value: Picked; onChange: (v: Picked) => void; placeholder?: string; allowExternal?: boolean; single?: boolean; autoFocus?: boolean; label: string;
}) {
  const [q, setQ] = useState(""), [rows, setRows] = useState<Person[]>([]), [hi, setHi] = useState(0), [open, setOpen] = useState(false);
  const id = useId(), box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!q.trim()) { setRows([]); return; }
    const t = setTimeout(() => world.get<{ items: Person[] }>(`/directory/people?q=${encodeURIComponent(q)}&limit=8`, s)
      .then((r) => { setRows(r.items.filter((p) => !value.people.some((v) => v.id === p.id) && p.id !== s.user.id)); setHi(0); }).catch(() => setRows([])), 150);
    return () => clearTimeout(t);
  }, [q, s, value.people]);
  useEffect(() => { const f = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); }; document.addEventListener("mousedown", f); return () => document.removeEventListener("mousedown", f); }, []);
  const addPerson = (p: Person) => { onChange({ ...value, people: single ? [p] : [...value.people, p] }); setQ(""); setRows([]); };
  const addExternal = () => { const v = q.trim(); if (allowExternal && EMAIL.test(v) && !value.external.includes(v)) { onChange({ ...value, external: [...value.external, v] }); setQ(""); } };
  const key = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setHi((h) => Math.min(h + 1, rows.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (rows[hi]) addPerson(rows[hi]); else addExternal(); }
    else if (e.key === "Escape") setOpen(false);
    else if (e.key === "Backspace" && !q) { if (value.external.length) onChange({ ...value, external: value.external.slice(0, -1) }); else if (value.people.length) onChange({ ...value, people: value.people.slice(0, -1) }); }
  };
  return (
    <div className="picker" ref={box}>
      <label className="small muted" htmlFor={id}>{label}</label>
      <div className="picker-box">
        {value.people.map((p) => <span key={p.id} className="chip pchip"><b>{p.name}</b><span className="muted">{p.unit}</span>
          <button type="button" aria-label={`${p.name} 빼기`} onClick={() => onChange({ ...value, people: value.people.filter((x) => x.id !== p.id) })}>×</button></span>)}
        {value.external.map((a) => <span key={a} className="chip pchip warn"><b>{a}</b><span>외부</span>
          <button type="button" aria-label={`${a} 빼기`} onClick={() => onChange({ ...value, external: value.external.filter((x) => x !== a) })}>×</button></span>)}
        {!(single && value.people.length) && <input id={id} value={q} autoFocus={autoFocus} placeholder={value.people.length || value.external.length ? "" : placeholder}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }} onKeyDown={key} onFocus={() => setOpen(true)} role="combobox" aria-expanded={open && rows.length > 0} aria-controls={`${id}-list`} autoComplete="off" />}
      </div>
      {open && (rows.length > 0 || (allowExternal && EMAIL.test(q.trim()))) && (
        <ul className="picker-list" id={`${id}-list`} role="listbox">
          {rows.map((p, i) => <li key={p.id} role="option" aria-selected={i === hi}><button type="button" className={i === hi ? "on" : ""} onMouseEnter={() => setHi(i)} onClick={() => addPerson(p)}>
            <Avatar name={p.name} /><span className="grow"><b>{p.name}</b> <span className="muted small">{p.position === "팀원" ? p.grade : p.position}</span><div className="small muted">{p.dept} · {p.unit}</div></span></button></li>)}
          {allowExternal && EMAIL.test(q.trim()) && <li><button type="button" onClick={addExternal}><span className="grow">외부 주소 <b>{q.trim()}</b> 추가</span></button></li>}
        </ul>)}
    </div>
  );
}
