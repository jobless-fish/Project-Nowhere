import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

const root = createRoot(document.getElementById("root")!);
const show = () => root.render(<StrictMode><App /></StrictMode>);

if (import.meta.env.VITE_STATIC) {
  // GitHub Pages demo: start the Python engine in the tab first, with a visible reason for the wait (and a readable failure).
  const box = document.createElement("div");
  box.setAttribute("role", "status");
  box.style.cssText = "max-width:520px;margin:20vh auto;padding:0 20px;font:600 18px/1.6 Pretendard,system-ui,sans-serif;color:#2b2a26";
  box.textContent = "노웨어 데모를 준비하는 중이에요…";
  document.getElementById("root")!.append(box);
  import("./static-demo").then(({ startStaticDemo }) => startStaticDemo((t) => { box.textContent = t; }))
    .then(() => show())
    .catch((e) => { box.textContent = `데모 엔진을 시작하지 못했어요. 페이지를 새로고침해 주세요. (${e instanceof Error ? e.message : e})`; });
} else show();
