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

export const world = {
  get: <T,>(path: string, s: Session) => req<T>(`/world${path}`, {}, s.token),
  post: <T,>(path: string, body: unknown, s?: Session) => req<T>(`/world${path}`, { method: "POST", body: JSON.stringify(body) }, s?.token),
};
export const api = {
  get: <T,>(path: string) => req<T>(`/api${path}`),
  post: <T,>(path: string, body: unknown) => req<T>(`/api${path}`, { method: "POST", body: JSON.stringify(body) }),
};
