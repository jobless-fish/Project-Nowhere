import { useState } from "react";

type Mode = "system" | "light" | "dark";
const ORDER: Mode[] = ["system", "light", "dark"];
const LABEL: Record<Mode, string> = { system: "자동", light: "라이트", dark: "다크" };
const ICON: Record<Mode, string> = { system: "🖥", light: "☀️", dark: "🌙" };

const read = (): Mode => { try { const t = localStorage.getItem("nw_theme"); return t === "light" || t === "dark" ? t : "system"; } catch { return "system"; } };
const apply = (m: Mode) => {
  if (m === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = m;
  try { m === "system" ? localStorage.removeItem("nw_theme") : localStorage.setItem("nw_theme", m); } catch { /* storage blocked: the choice lasts until reload */ }
};

/** system (follows the OS) -> light -> dark. Without this the app could only follow the operating system's setting. */
export default function ThemeToggle() {
  const [m, setM] = useState<Mode>(read);
  const next = () => { const n = ORDER[(ORDER.indexOf(m) + 1) % ORDER.length]; apply(n); setM(n); };
  return <button className="btn sm theme-toggle" onClick={next} aria-label={`화면 모드: ${LABEL[m]}. 누르면 바뀌어요`} title="화면 모드 바꾸기 (자동 → 라이트 → 다크)"><span aria-hidden="true">{ICON[m]}</span>{LABEL[m]}</button>;
}
