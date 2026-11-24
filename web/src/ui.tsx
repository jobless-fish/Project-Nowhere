import type { ReactNode } from "react";
import type { SourceInfo } from "./types";

const P: Record<string, string> = {
  home: "M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  org: "M9 3h6v5H9zM3 16h6v5H3zM15 16h6v5h-6zM12 8v4M6 16v-4h12v4",
  news: "M4 5h13v14H6a2 2 0 01-2-2V5zM17 8h3v9a2 2 0 01-2 2M8 9h5M8 13h5",
  mail: "M3 6h18v12H3zM3 7l9 7 9-7",
  chat: "M4 5h16v11H9l-5 4V5z",
  admin: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3zM9 12l2 2 4-4",
  out: "M10 4H5v16h5M15 8l4 4-4 4M9 12h10",
  clock: "M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  check: "M5 12l4 4 10-10",
  warn: "M12 4l10 17H2L12 4zM12 10v5M12 18v.5",
};
export const Icon = ({ n, size = 18 }: { n: keyof typeof P; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={P[n]} /></svg>
);

export const Avatar = ({ name }: { name: string }) => <span className="avatar" aria-hidden="true">{name.slice(0, 1)}</span>;
export const Badge = ({ kind = "", children }: { kind?: string; children: ReactNode }) => <span className={`badge ${kind}`}>{children}</span>;
export const Card = ({ kind = "", children, guide }: { kind?: string; children: ReactNode; guide?: string }) => <section className={`card ${kind}`} data-guide={guide}>{children}</section>;
export const PageHead = ({ title, sub, guide }: { title: string; sub?: string; guide?: string }) => (
  <header className="page-head" data-guide={guide}><h1>{title}</h1>{sub && <p>{sub}</p>}</header>
);
export const Empty = ({ children }: { children: ReactNode }) => <div className="empty">{children}</div>;
export const Skeletons = ({ n = 3 }: { n?: number }) => (
  <div className="stack" aria-busy="true" aria-label="불러오는 중">{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton" style={{ height: 64 }} />)}</div>
);

const SRC: Record<string, string> = { mail: "메일", issue: "이슈", notice: "공지", post: "게시판", chat: "메신저", slack: "메신저" };
export const SourceChip = ({ id, sources }: { id: string; sources: Record<string, SourceInfo> }) => {
  const s = sources[id];
  return <span className="chip" title={s ? `${s.sender}` : id}><b>{SRC[s?.source] ?? "기타"}</b><span className="trunc">{s?.title ?? id}</span></span>;
};

export const Check = ({ on, onChange, label }: { on: boolean; onChange: () => void; label: string }) => (
  <button type="button" role="checkbox" aria-checked={on} aria-label={label} className="check" onClick={onChange}><span className="box">{on && <Icon n="check" size={14} />}</span></button>
);

export const ago = (iso: string) => {
  const h = (Date.now() - new Date(iso).getTime()) / 3.6e6;
  return h < 1 ? "방금" : h < 24 ? `${Math.floor(h)}시간 전` : `${Math.floor(h / 24)}일 전`;
};

export const Failed = ({ what, onRetry }: { what: string; onRetry: () => void }) => (
  <div className="empty" role="alert"><p>{what}을(를) 불러오지 못했어요. 서버 연결을 확인한 뒤 다시 시도해 주세요.</p><button className="btn sm" onClick={onRetry}>다시 시도</button></div>
);
