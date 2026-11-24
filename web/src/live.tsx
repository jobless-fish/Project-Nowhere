import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, world } from "./api";
import type { Mail, Session } from "./types";

export type Toast = { id: number; text: string; actions?: { label: string; run: () => void }[]; kind?: "info" | "ok" | "warn" };
type Live = {
  mail: number; chat: number; byChannel: Record<string, number>; typing: boolean;
  poke: () => void; toast: (t: Omit<Toast, "id">) => void;
};
const Ctx = createContext<Live>({ mail: 0, chat: 0, byChannel: {}, typing: false, poke: () => {}, toast: () => {} });
export const useLive = () => useContext(Ctx);

/** Polls "what is new" (mail, chat) and shows it: nav badges, a "someone replied" toast, and the typing hint. Pauses while the tab is hidden. */
export function LiveProvider({ s, children }: { s: Session; children: ReactNode }) {
  const [st, setSt] = useState({ mail: 0, chat: 0, byChannel: {} as Record<string, number>, typing: false });
  const [toasts, setToasts] = useState<Toast[]>([]);
  const lastMail = useRef<string | null>(null), primed = useRef(false), timer = useRef<number>(0), n = useRef(0);

  const toast = useCallback((t: Omit<Toast, "id">) => {
    const id = ++n.current;
    setToasts((x) => [...x.slice(-2), { ...t, id }]);
    window.setTimeout(() => setToasts((x) => x.filter((y) => y.id !== id)), t.actions ? 9000 : 5000);
  }, []);

  const tick = useCallback(async () => {
    if (document.hidden) return;
    try {
      const [m, c] = await Promise.all([world.get<{ count: number; latest: Mail | null; typing: boolean }>("/mail/unread", s), world.get<{ total: number; by_channel: Record<string, number>; typing: boolean }>("/chat/unread", s)]);
      setSt({ mail: m.count, chat: c.total, byChannel: c.by_channel, typing: m.typing || c.typing });
      if (m.latest && m.latest.id !== lastMail.current) {
        if (primed.current) {
          const who = m.latest.from.name;
          toast({ text: `새 메일 · ${who}: ${m.latest.subject}`, kind: "info", actions: [
            { label: "열기", run: () => { window.location.hash = `#/mail?open=${m.latest!.id}`; } },
            { label: "브리핑 갱신", run: () => { void api.post("/assistant/briefing/refresh", { user_id: s.user.id }).then(() => window.dispatchEvent(new Event("briefing:changed"))).catch(() => {}); } },
          ] });
        }
        lastMail.current = m.latest.id;
      }
      primed.current = true;
    } catch { /* offline for a moment: try again next tick */ }
  }, [s, toast]);

  const schedule = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => { await tick(); schedule(); }, document.hidden ? 8000 : 4000);
  }, [tick]);
  const poke = useCallback(() => { void tick(); for (const ms of [1500, 4000, 8000, 14000]) window.setTimeout(() => void tick(), ms); }, [tick]);
  useEffect(() => { void tick(); schedule(); return () => window.clearTimeout(timer.current); }, [tick, schedule]);

  return (
    <Ctx.Provider value={{ ...st, poke, toast }}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind ?? "info"}`}>
            <span>{t.text}</span>
            {t.actions?.map((a) => <button key={a.label} className="btn sm" onClick={() => { a.run(); setToasts((x) => x.filter((y) => y.id !== t.id)); }}>{a.label}</button>)}
            <button className="btn quiet sm" aria-label="알림 닫기" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}>×</button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
