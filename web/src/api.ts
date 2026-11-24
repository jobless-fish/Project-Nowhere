import type { Session } from "./types";

const KEY = "nw_session";
export const getSession = (): Session | null => {
  try { return JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch { return null; }
};
export const setSession = (s: Session | null) => {
  try { s ? sessionStorage.setItem(KEY, JSON.stringify(s)) : sessionStorage.removeItem(KEY); } catch { /* storage blocked */ }
};

export class ApiError extends Error {
  constructor(public status: number, msg: string) { super(msg); }
}

async function req<T>(url: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(url, { ...init, headers: { ...headers, ...(init.headers as object) } });
  if (!r.ok) throw new ApiError(r.status, (await r.text()).slice(0, 200));
  return r.json();
}

/** A readable message from an API error ({"detail": "..."} -> the sentence). */
export const errText = (e: unknown, fallback = "처리하지 못했어요. 잠시 뒤에 다시 해 주세요."): string => {
  if (!(e instanceof ApiError)) return fallback;
  try { const d = JSON.parse(e.message).detail; if (typeof d === "string") return d; } catch { /* not JSON */ }
  return e.message && e.message.length < 140 ? e.message : fallback;
};

export const world = {
  get: <T,>(path: string, s: Session) => req<T>(`/world${path}`, {}, s.token),
  post: <T,>(path: string, body: unknown, s?: Session) => req<T>(`/world${path}`, { method: "POST", body: JSON.stringify(body) }, s?.token),
  patch: <T,>(path: string, body: unknown, s: Session) => req<T>(`/world${path}`, { method: "PATCH", body: JSON.stringify(body) }, s.token),
};
export const api = {
  get: <T,>(path: string) => req<T>(`/api${path}`),
  post: <T,>(path: string, body: unknown) => req<T>(`/api${path}`, { method: "POST", body: JSON.stringify(body) }),
};
