import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { ActionStats, AutonomyRow, Doc, EvalSummary, Metrics } from "../types";
import { Badge, Card, Empty, PageHead, Skeletons } from "../ui";

const MODES = ["shadow", "assisted", "auto"];
const MODE_KO: Record<string, string> = { shadow: "그림자", assisted: "보조", auto: "자동" };
const TYPE_KO: Record<string, string> = { expense_claim: "경비 정산", leave_request: "휴가 신청", purchase_request: "구매 요청", inquiry: "사내 문의", other: "기타" };
const REASON = (t: string) => t.startsWith("collecting") ? "표본을 모으는 중입니다" : t.replace(/agreement lower bound ([\d.]+) >= ([\d.]+)/, "일치율 신뢰구간 하한 $1 ≥ 기준 $2").replace(/recent agreement (\d+)\/(\d+) too low/, "최근 일치 $1/$2건으로 기준 미달");
const NEED: Record<string, number> = { shadow: 20, assisted: 30 };

function Autonomy() {
  const [rows, setRows] = useState<AutonomyRow[] | null>(null);
  const load = useCallback(() => api.get<AutonomyRow[]>("/autonomy").then(setRows).catch(() => setRows([])), []);
  useEffect(() => { load(); }, [load]);
  const promote = async (r: AutonomyRow) => { await api.post(`/autonomy/${r.doc_type}/mode`, { mode: r.recommended_mode }); load(); };
  if (!rows) return <Skeletons />;
  return (
    <div className="stack">
      <p className="muted small">AI는 사람과의 일치율로만 자율권을 얻습니다. 승격은 추천만 하고 담당자가 승인하며, 품질이 떨어지면 자동으로 강등됩니다.</p>
      {rows.map((r) => (
        <Card key={r.doc_type}><div className="stack" style={{ gap: 10 }}>
          <div className="row wrap"><b className="grow">{TYPE_KO[r.doc_type] ?? r.doc_type}</b>
            <span className="seg" role="img" aria-label={`현재 단계 ${MODE_KO[r.mode]}`}>{MODES.map((m) => <span key={m} className={m === r.mode ? "on" : ""}>{MODE_KO[m]}</span>)}</span></div>
          {NEED[r.mode] && <div><div className="progress" role="progressbar" aria-valuenow={r.samples} aria-valuemax={NEED[r.mode]}>
            <i style={{ width: `${Math.min(100, (r.samples / NEED[r.mode]) * 100)}%` }} /></div>
            <p className="small muted" style={{ marginTop: 4 }}>표본 {r.samples}/{NEED[r.mode]}건 · 일치 {r.agree}건 · 신뢰구간 하한 {r.lower_bound}</p></div>}
          {r.mode === "auto" && <p className="small muted">자동 단계 · 최근 결과 신뢰구간 하한 {r.lower_bound}{r.applied && " · 자동 강등됨"}</p>}
          <div className="row"><span className="small muted grow">{REASON(r.reason)}</span>
            {r.recommended_mode !== r.mode && <button className="btn primary sm" onClick={() => promote(r)}>{MODE_KO[r.recommended_mode]}로 승격 승인</button>}</div>
        </div></Card>))}
    </div>
  );
}

function Ops() {
  const [m, setM] = useState<Metrics | null>(null);
  useEffect(() => { api.get<Metrics>("/metrics").then(setM).catch(() => {}); }, []);
  if (!m) return <Skeletons n={2} />;
  const S = ({ v, l }: { v: string | number; l: string }) => <div className="card stat"><b>{v}</b><span>{l}</span></div>;
  return (
    <div className="stack">
      <div className="grid">
        <S v={`${Math.round(m.auto_processed_rate * 100)}%`} l="자동 처리율" /><S v={m.llm_calls} l="LLM 호출" />
        <S v={`${Math.round(m.llm_success_rate * 100)}%`} l="호출 성공률" /><S v={`${m.avg_latency_ms}ms`} l="평균 지연" />
        <S v={`${m.p95_latency_ms}ms`} l="p95 지연" /><S v={`$${m.total_cost_usd}`} l="누적 비용" />
      </div>
      <p className="small muted">프롬프트 버전 <Badge>{m.prompt_version}</Badge> · 배포 전 평가셋(eval/)으로 회귀를 확인합니다.</p>
    </div>
  );
}

function Proposals() {
  const [st, setSt] = useState<ActionStats | null>(null);
  useEffect(() => { api.get<ActionStats>("/assistant/actions/stats").then(setSt).catch(() => {}); }, []);
  if (!st) return <Skeletons n={2} />;
  const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);
  const S = ({ v, l }: { v: string | number; l: string }) => <div className="card stat"><b>{v}</b><span>{l}</span></div>;
  return (
    <div className="stack">
      <p className="muted small">비서는 초안만 만들고, 발송은 사람이 승인해야 이뤄집니다. 승인 그대로 보낸 비율이 높아질수록 이 업무는 자동화 후보가 됩니다.</p>
      <div className="grid"><S v={pct(st.acceptance_rate)} l="초안 그대로 발송" /><S v={pct(st.usable_rate)} l="수정 포함 발송" />
        <S v={st.sent_as_is} l="그대로 발송" /><S v={st.sent_edited} l="수정 후 발송" /><S v={st.rejected} l="반려" /><S v={st.blocked} l="차단(민감 표현)" /></div>
      {st.failed > 0 && <p className="small" role="alert">발송 실패 {st.failed}건이 있습니다.</p>}
    </div>
  );
}

const CASE_KO: Record<string, string> = { "todo:positive": "할일 · 맞았음(완료)", "todo:negative": "할일 · 틀렸음(관련 없음)",
  "reply:accepted": "초안 · 그대로 발송", "reply:edited": "초안 · 사람이 수정", "reply:rejected": "초안 · 반려" };

function Learning() {
  const [sm, setSm] = useState<EvalSummary | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get<EvalSummary>("/assistant/eval/summary").then(setSm).catch(() => {}); }, []);
  const harvest = async () => { setBusy(true); try { setSm(await api.post<EvalSummary>("/assistant/eval/harvest", {})); } catch { /* keep old */ } setBusy(false); };
  if (!sm) return <Skeletons n={2} />;
  return (
    <div className="stack">
      <p className="muted small">사용자가 누른 "관련 없음"과 초안 수정·반려는 평가 사례가 됩니다. 프롬프트나 규칙을 바꿀 때마다 이 사례로 다시 채점하고,
        점수가 기준선보다 떨어지면 배포를 막습니다 (<code>python -m eval.feedback_eval</code>).</p>
      <div className="row"><button className="btn primary" onClick={harvest} disabled={busy}>{busy ? "모으는 중…" : "피드백에서 평가 사례 모으기"}</button>
        {sm.new && <span className="small muted">새 사례: 할일 {sm.new.todo}건 · 초안 {sm.new.reply}건</span>}</div>
      {sm.total === 0 ? <Empty>아직 모은 사례가 없습니다. 홈에서 할일을 완료하거나 "관련 없음"을 누르고, 초안을 수정해 보세요.</Empty> :
        <div className="grid">{Object.entries(sm.by).map(([k, n]) => <div key={k} className="card stat"><b>{n}</b><span>{CASE_KO[k] ?? k}</span></div>)}</div>}
      <p className="small faint">실제 서비스에서는 사례 수집 전에 직원 동의, 개인정보 마스킹, 보관 기간 정책이 필요합니다.</p>
    </div>
  );
}

function Docs() {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api.get<Doc[]>("/documents").then(setDocs).catch(() => setDocs([])), []);
  useEffect(() => { load(); }, [load]);
  const submit = async () => { if (!text.trim()) return; setBusy(true); await api.post("/documents", { text, source: "console" }).catch(() => {}); setText(""); setBusy(false); load(); };
  const review = async (id: number, approve: boolean) => { await api.post(`/documents/${id}/review`, { approve, reviewer: "console" }).catch(() => {}); load(); };
  const KIND: Record<string, string> = { processed: "ok", approved: "ok", needs_review: "warn", failed: "urgent", rejected: "urgent" };
  return (
    <div className="stack">
      <Card><div className="stack"><label htmlFor="doc" className="small muted">요청서·메일 내용을 붙여 넣으면 분류하고 필요한 시스템에 연계합니다.</label>
        <textarea id="doc" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="예) 박서연입니다. 출장비 정산 요청합니다. 총 85만원" />
        <div><button className="btn primary" onClick={submit} disabled={busy || !text.trim()}>제출</button></div></div></Card>
      {!docs ? <Skeletons n={2} /> : docs.length === 0 ? <Empty>처리한 문서가 없습니다.</Empty> : docs.map((d) => (
        <Card key={d.id} kind="flat"><div className="stack" style={{ gap: 6 }}>
          <div className="row wrap"><Badge kind={KIND[d.status] ?? ""}>{d.status}</Badge>
            <b>{TYPE_KO[d.extraction?.doc_type ?? "other"]}</b>{d.extraction && <span className="small muted">신뢰도 {d.extraction.confidence}</span>}
            {d.erp_ref && <span className="chip">{d.erp_ref}</span>}</div>
          <p className="small muted">{d.text.slice(0, 140)}</p>
          {d.status === "needs_review" && <div className="row"><button className="btn primary sm" onClick={() => review(d.id, true)}>승인</button>
            <button className="btn sm" onClick={() => review(d.id, false)}>반려</button><span className="small muted">{d.audit.at(-1)?.reason}</span></div>}
        </div></Card>))}
    </div>
  );
}

export default function Admin() {
  const [tab, setTab] = useState("auto");
  const T = [["auto", "자동화 단계"], ["ops", "운영 지표"], ["docs", "문서 처리"], ["acts", "비서 제안"], ["learn", "학습 데이터"]];
  return (
    <>
      <PageHead title="관리자 콘솔" sub="AI 자동화의 신뢰를 측정하고 단계를 관리합니다." />
      <div className="tabs" role="tablist">{T.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "auto" ? <Autonomy /> : tab === "ops" ? <Ops /> : tab === "acts" ? <Proposals /> : tab === "learn" ? <Learning /> : <Docs />}
    </>
  );
}
