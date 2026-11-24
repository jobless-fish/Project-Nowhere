import { useCallback, useEffect, useState } from "react";
import { api, errText } from "../api";
import { useLive } from "../live";
import type { ActionStats, AutonomyRow, Doc, EvalSummary, Metrics, MuteCandidate } from "../types";
import { Badge, Card, Empty, PageHead, Skeletons, Failed } from "../ui";

const nf = new Intl.NumberFormat("ko-KR");
const pct0 = (v: number) => `${nf.format(Math.round(v * 100))}%`;

const MODES = ["shadow", "assisted", "auto"];
const MODE_KO: Record<string, string> = { shadow: "그림자", assisted: "보조", auto: "자동" };
// Reply drafts use the same ladder, but "auto" only means pre-drafted: a person still presses send.
const REPLY_KO: Record<string, string> = { assisted: "제안", auto: "미리 작성" };
// 으로/로 by the last syllable (받침 없음 또는 ㄹ -> 로)
const ro = (w: string) => { const j = (w.charCodeAt(w.length - 1) - 0xac00) % 28; return j === 0 || j === 8 ? "로" : "으로"; };
const isReply = (t: string) => t.startsWith("reply_");
const modeName = (t: string, m: string) => (isReply(t) ? REPLY_KO[m] : MODE_KO[m]);
const TYPE_KO: Record<string, string> = { reply_internal: "회신 초안 (사내 수신자)", expense_claim: "경비 정산", leave_request: "휴가 신청", purchase_request: "구매 요청", inquiry: "사내 문의", other: "기타" };
const REASON = (t: string) => t.startsWith("collecting") ? "표본을 모으는 중입니다" : t.replace(/agreement lower bound ([\d.]+) >= ([\d.]+)/, "일치율 신뢰구간 하한 $1 ≥ 기준 $2").replace(/recent agreement (\d+)\/(\d+) too low/, "최근 일치 $1/$2건으로 기준 미달");
const NEED = (t: string, m: string) => (m === "shadow" ? 20 : m === "assisted" ? (isReply(t) ? 20 : 30) : 0);

const NEED_LB = (t: string, m: string) => (m === "shadow" ? 0.85 : isReply(t) ? 0.8 : 0.95);
/** Why the type is where it is, in plain words, with what is still missing. */
const WHY = (r: AutonomyRow) => {
  if (r.reason.startsWith("collecting")) {
    if (r.mode === "auto") return "최근 결과가 기준 이상이라 자동 단계를 유지해요";
    const n = NEED(r.doc_type, r.mode), lb = NEED_LB(r.doc_type, r.mode);
    if (r.samples < n) return `표본이 ${n - r.samples}건 더 쌓이면 승격 심사 대상이 돼요 (지금 ${r.samples}건)`;
    return `표본은 충분하지만 일치율 신뢰구간 하한 ${r.lower_bound}이 기준 ${lb}에 못 미쳐요. 맞는 결과가 더 쌓여야 해요`;
  }
  return REASON(r.reason);
};

function Autonomy() {
  const live = useLive();
  const [rows, setRows] = useState<AutonomyRow[] | null>(null);
  const [bad, setBad] = useState(false);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState<{ type: string; text: string } | null>(null);
  const load = useCallback(() => { setBad(false); return api.get<AutonomyRow[]>("/autonomy").then(setRows).catch(() => setBad(true)); }, []);
  useEffect(() => { load(); }, [load]);
  const setMode = async (r: AutonomyRow, mode: string, how: "approve" | "manual") => {
    setBusy(r.doc_type); setErr(null);
    try {
      await api.post(`/autonomy/${r.doc_type}/mode`, { mode });
      await load();
      live.toast({ kind: "ok", text: `${TYPE_KO[r.doc_type] ?? r.doc_type}: ${modeName(r.doc_type, mode)} 단계로 ${how === "approve" ? "승격했어요" : "바꿨어요"}.` });
    } catch (e) { setErr({ type: r.doc_type, text: errText(e, "단계를 바꾸지 못했어요. 서버 연결과 권한을 확인해 주세요.") }); }
    setBusy("");
  };
  const click = (r: AutonomyRow, m: string) => {
    if (m === r.mode) return;
    const order = isReply(r.doc_type) ? ["assisted", "auto"] : MODES;
    if (order.indexOf(m) > order.indexOf(r.mode) && m !== r.recommended_mode &&
        !window.confirm(`근거(일치율)가 아직 기준에 못 미쳤어요.\n그래도 '${modeName(r.doc_type, m)}' 단계로 올릴까요? 사람이 직접 올린 것으로 기록돼요.`)) return;
    void setMode(r, m, m === r.recommended_mode && order.indexOf(m) > order.indexOf(r.mode) ? "approve" : "manual");
  };
  if (bad) return <Failed what="자동화 단계" onRetry={load} />;
  if (!rows) return <Skeletons />;
  return (
    <div className="stack">
      <p className="muted small">AI는 사람과의 일치율로만 자율권을 얻습니다. 승격은 추천만 하고 담당자가 승인하며, 품질이 떨어지면 자동으로 강등됩니다. 단계 이름을 눌러 직접 바꿀 수도 있어요(근거 없이 올리면 확인을 한 번 더 물어봐요).</p>
      {rows.map((r) => {
        const order = isReply(r.doc_type) ? ["assisted", "auto"] : MODES;
        return (
        <Card key={r.doc_type}><div className="stack" style={{ gap: 10 }}>
          <div className="row wrap"><b className="grow">{TYPE_KO[r.doc_type] ?? r.doc_type}</b>
            <div className="seg" role="group" aria-label={`${TYPE_KO[r.doc_type] ?? r.doc_type} 단계`}>{order.map((m) => <button key={m} type="button" className={m === r.mode ? "on" : ""} aria-pressed={m === r.mode} disabled={busy === r.doc_type} onClick={() => click(r, m)}>{modeName(r.doc_type, m)}</button>)}</div></div>
          {NEED(r.doc_type, r.mode) > 0 && <div><div className="progress" role="progressbar" aria-valuenow={r.samples} aria-valuemax={NEED(r.doc_type, r.mode)}>
            <i style={{ width: `${Math.min(100, (r.samples / NEED(r.doc_type, r.mode)) * 100)}%` }} /></div>
            <p className="small muted" style={{ marginTop: 4 }}>표본 {Math.min(r.samples, NEED(r.doc_type, r.mode))}/{NEED(r.doc_type, r.mode)}건{r.samples >= NEED(r.doc_type, r.mode) ? ` 충족(총 ${r.samples}건)` : ""} · {isReply(r.doc_type) ? "초안 그대로 발송" : "일치"} {r.agree}건 · 신뢰구간 하한 {r.lower_bound}</p></div>}
          {isReply(r.doc_type) && <p className="small muted">미리 작성 단계가 되면 출근할 때 사내 수신자 초안을 먼저 만들어 둬요. 발송은 항상 사람이 눌러요. 외부 수신자는 승격 대상이 아니에요.</p>}
          {r.mode === "auto" && <p className="small muted">자동 단계 · 최근 결과 신뢰구간 하한 {r.lower_bound}{r.applied && " · 자동 강등됨"}</p>}
          <div className="row wrap"><span className="small muted grow">{WHY(r)}</span>
            {r.recommended_mode !== r.mode && <button className="btn primary sm" disabled={busy === r.doc_type} onClick={() => setMode(r, r.recommended_mode, "approve")}>{modeName(r.doc_type, r.recommended_mode)}{ro(modeName(r.doc_type, r.recommended_mode))} 승격 승인</button>}</div>
          {err?.type === r.doc_type && <p className="small" role="alert" style={{ color: "var(--danger)" }}>{err.text}</p>}
        </div></Card>);
      })}
    </div>
  );
}

function Ops() {
  const [m, setM] = useState<Metrics | null>(null);
  const [bad, setBad] = useState(false);
  const load = useCallback(() => { setBad(false); api.get<Metrics>("/metrics").then(setM).catch(() => setBad(true)); }, []);
  useEffect(() => { load(); }, [load]);
  if (bad) return <Failed what="운영 지표" onRetry={load} />;
  if (!m) return <Skeletons n={2} />;
  const Minor = ({ v, l }: { v: string; l: string }) => <div className="card stat minor"><b>{v}</b><span>{l}</span></div>;
  return (
    <div className="stack">
      <p className="muted small">이 화면의 질문: <b>AI가 사람 손을 얼마나 덜어 주고, 그만큼 믿을 만한가?</b></p>
      <div className="card stat lead"><span>자동 처리율 · 전체 문서 중 사람 확인 없이 끝난 비율</span><b>{pct0(m.auto_processed_rate)}</b></div>
      <div className="grid">
        <Minor v={pct0(m.llm_success_rate)} l="LLM 호출 성공률" /><Minor v={`${nf.format(m.avg_latency_ms)}ms`} l="평균 지연" />
        <Minor v={`${nf.format(m.p95_latency_ms)}ms`} l="p95 지연 (느린 5%의 기준선)" /><Minor v={nf.format(m.llm_calls)} l="LLM 호출 수" />
        <Minor v={`$${nf.format(m.total_cost_usd)}`} l="누적 비용" />
      </div>
      <p className="small muted">프롬프트 버전 <Badge>{m.prompt_version}</Badge> · 배포 전 평가셋(eval/)으로 회귀를 확인합니다.</p>
    </div>
  );
}

function Proposals() {
  const [st, setSt] = useState<ActionStats | null>(null);
  const [bad, setBad] = useState(false);
  const load = useCallback(() => { setBad(false); api.get<ActionStats>("/assistant/actions/stats").then(setSt).catch(() => setBad(true)); }, []);
  useEffect(() => { load(); }, [load]);
  if (bad) return <Failed what="비서 제안 통계" onRetry={load} />;
  if (!st) return <Skeletons n={2} />;
  const pct = (v: number | null) => (v === null ? "—" : pct0(v));
  const S = ({ v, l }: { v: string | number; l: string }) => <div className="card stat"><b>{v}</b><span>{l}</span></div>;
  return (
    <div className="stack">
      <p className="muted small">비서는 초안만 만들고, 발송은 사람이 승인해야 이뤄집니다. 승인 그대로 보낸 비율이 높아질수록 이 업무는 자동화 후보가 됩니다.</p>
      <div className="grid"><S v={pct(st.acceptance_rate)} l="초안 그대로 발송" /><S v={pct(st.usable_rate)} l="수정 포함 발송" />
        <S v={nf.format(st.sent_as_is)} l="그대로 발송" /><S v={nf.format(st.sent_edited)} l="수정 후 발송" /><S v={nf.format(st.rejected)} l="반려" /><S v={nf.format(st.blocked)} l="차단(민감 표현)" /></div>
      {st.failed > 0 && <p className="small" role="alert">발송 실패 {st.failed}건이 있습니다.</p>}
    </div>
  );
}

const CASE_KO: Record<string, string> = { "todo:positive": "할일 · 맞았음(완료)", "todo:negative": "할일 · 틀렸음(관련 없음)",
  "reply:accepted": "초안 · 그대로 발송", "reply:edited": "초안 · 사람이 수정", "reply:rejected": "초안 · 반려" };

function Candidates() {
  const [c, setC] = useState<MuteCandidate[] | null>(null);
  useEffect(() => { api.get<{ items: MuteCandidate[] }>("/assistant/mutes/candidates").then((r) => setC(r.items)).catch(() => setC([])); }, []);
  if (!c || c.length === 0) return null;
  return (
    <Card kind="flat"><div className="stack" style={{ gap: 8 }}>
      <b>여러 명이 "관련 없음"으로 숨긴 종류 — 규칙 검토 후보</b>
      <p className="small muted">한 사람의 클릭은 그 사람에게만 적용돼요. 여러 사람이 같은 종류를 숨기면 여기에 올라오고, 규칙을 바꿀지는 사람이 정해요(자동으로 바뀌지 않아요).</p>
      {c.map((x) => <div key={x.sig} className="row wrap"><span className="grow">{x.title}</span><Badge>{x.source === "mail" ? "메일" : x.source === "notice" ? "공지" : x.source}</Badge><span className="small muted">{x.users}명</span></div>)}
    </div></Card>
  );
}

function Learning() {
  const [sm, setSm] = useState<EvalSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [bad, setBad] = useState(false);
  const load = useCallback(() => { setBad(false); api.get<EvalSummary>("/assistant/eval/summary").then(setSm).catch(() => setBad(true)); }, []);
  useEffect(() => { load(); }, [load]);
  const harvest = async () => { setBusy(true); try { setSm(await api.post<EvalSummary>("/assistant/eval/harvest", {})); } catch { /* keep old */ } setBusy(false); };
  if (bad) return <Failed what="학습 데이터" onRetry={load} />;
  if (!sm) return <Skeletons n={2} />;
  return (
    <div className="stack">
      <p className="muted small">사용자가 누른 "관련 없음"과 초안 수정·반려는 평가 사례가 됩니다. 프롬프트나 규칙을 바꿀 때마다 이 사례로 다시 채점하고,
        점수가 기준선보다 떨어지면 배포를 막습니다 (<code>python -m eval.feedback_eval</code>).</p>
      <div className="row"><button className="btn primary" onClick={harvest} disabled={busy}>{busy ? "모으는 중…" : "피드백에서 평가 사례 모으기"}</button>
        {sm.new && <span className="small muted">새 사례: 할일 {sm.new.todo}건 · 초안 {sm.new.reply}건</span>}</div>
      {sm.total === 0 ? <Empty>아직 모은 사례가 없습니다. 홈에서 할일을 완료하거나 "관련 없음"을 누르고, 초안을 수정해 보세요.</Empty> :
        <div className="grid">{Object.entries(sm.by).map(([k, n]) => <div key={k} className="card stat"><b>{n}</b><span>{CASE_KO[k] ?? k}</span></div>)}</div>}
      <Candidates />
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
      <div className="tabs" role="tablist" data-guide="admin-tabs">{T.map(([k, l]) => <button key={k} data-guide={`admin-tab-${k}`} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "auto" ? <Autonomy /> : tab === "ops" ? <Ops /> : tab === "acts" ? <Proposals /> : tab === "learn" ? <Learning /> : <Docs />}
    </>
  );
}
