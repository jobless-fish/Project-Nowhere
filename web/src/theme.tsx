import { useState } from "react";

type Mode = "light" | "dark" | "auto";
const ORDER: Mode[] = ["light", "dark", "auto"];
const LABEL: Record<Mode, string> = { light: "라이트", dark: "다크", auto: "자동" };
const ICON: Record<Mode, string> = { light: "☀️", dark: "🌙", auto: "🖥" };

// light is the default, even when the operating system is dark; "auto" is opt-in
const read = (): Mode => { try { const t = localStorage.getItem("nw_theme"); return t === "dark" || t === "auto" ? t : "light"; } catch { return "light"; } };
const apply = (m: Mode) => {
  if (m === "light") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = m;
  try { m === "light" ? localStorage.removeItem("nw_theme") : localStorage.setItem("nw_theme", m); } catch { /* storage blocked: the choice lasts until reload */ }
};

/** light (default) -> dark -> auto (follows the operating system). */
export default function ThemeToggle() {
  const [m, setM] = useState<Mode>(read);
  const next = () => { const n = ORDER[(ORDER.indexOf(m) + 1) % ORDER.length]; apply(n); setM(n); };
  return <button className="btn sm theme-toggle" onClick={next} aria-label={`화면 모드: ${LABEL[m]}. 누르면 바뀌어요`} title="화면 모드 바꾸기 (라이트 → 다크 → 자동)"><span aria-hidden="true">{ICON[m]}</span>{LABEL[m]}</button>;
}
