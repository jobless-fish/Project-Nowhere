import { Icon, PageHead } from "../ui";

// Every control in every state, side by side on the same background. Used to eyeball (and screenshot) the rulebook.
const STATES = [["default", ""], ["hover", "is-hover"], ["active", "is-active"], ["focus", "is-focus"], ["disabled", "is-disabled"], ["loading", ""]] as const;
const VARIANTS = [["보조", ""], ["강조", "primary"], ["조용한", "quiet"]] as const;

export default function Controls() {
  return (
    <>
      <PageHead title="컨트롤 상태" sub="버튼·체크박스·입력창의 상태를 한 장에서 확인해요. 모든 컨트롤은 최소 44px, 눌림은 transform으로만 표현해요." />
      <div className="card"><div className="sheet" role="table" aria-label="컨트롤 상태 표">
        <span className="hd" />{STATES.map(([n]) => <span key={n} className="hd">{n === "loading" ? "loading · on" : n}</span>)}
        {VARIANTS.map(([label, cls]) => (
          <div key={label} style={{ display: "contents" }}>
            <span className="small muted">버튼 · {label}</span>
            {STATES.map(([n, st]) => (
              <div className="cell" key={n}><button className={`btn ${cls} ${st}`} disabled={n === "disabled"} aria-busy={n === "loading" || undefined}>
                {n === "loading" ? "저장" : <><Icon n="check" size={16} />확인</>}</button></div>
            ))}
          </div>
        ))}
        <span className="small muted">체크박스</span>
        {STATES.map(([n, st], i) => (
          <div className="cell" key={n}><button type="button" role="checkbox" aria-checked={i === 5} aria-label={i === 5 ? "on" : n} disabled={n === "disabled"}
            className={`check ${st}`}><span className="box">{i === 5 && <Icon n="check" size={14} />}</span></button></div>
        ))}
        <span className="small muted">입력창</span>
        {STATES.map(([n, st]) => (
          <div className="cell" key={n}>{n === "loading" ? <span className="small faint">—</span> :
            <input aria-label={n} className={st === "is-focus" ? "is-focus" : ""} defaultValue={n} disabled={n === "disabled"} style={st === "is-focus" ? { outline: "3px solid var(--focus)", outlineOffset: 2 } : undefined} />}</div>
        ))}
      </div></div>
    </>
  );
}
