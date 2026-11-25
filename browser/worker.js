// Runs the product in a Web Worker so the page stays responsive. Pyodide + its packages come from the official CDN (pinned) unless ?py=<dir> says otherwise.
const PYODIDE = "0.27.7";
let py, handle, ready;
const base = new URL(self.location.href);
const INDEX = base.searchParams.get("py") || `https://cdn.jsdelivr.net/pyodide/v${PYODIDE}/full/`;
const say = (text) => postMessage({ type: "progress", text });

async function boot() {
  importScripts(INDEX + "pyodide.js");
  say("파이썬 엔진을 내려받는 중이에요 (처음 한 번만 느려요)");
  py = await loadPyodide({ indexURL: INDEX });
  say("라이브러리를 준비하는 중이에요");
  await py.loadPackage(["typing-extensions", "annotated-types", "pydantic-core", "pydantic", "sniffio", "idna", "anyio", "certifi", "h11", "httpcore", "httpx", "sqlite3", "packaging"]);
  const wheels = ["starlette-0.41.3-py3-none-any.whl", "fastapi-0.115.6-py3-none-any.whl"].map((w) => new URL("wheels/" + w, base).href);
  await py.loadPackage(wheels);
  say("노웨어 회사 시스템과 비서를 켜는 중이에요");
  const zip = await (await fetch(new URL("nowhere-py.zip", base))).arrayBuffer();
  py.unpackArchive(zip, "zip", { extractDir: "/srv" });
  py.runPython("import sys; sys.path.insert(0, '/srv'); sys.path.insert(0, '/srv/browser'); import runpy; _b = runpy.run_path('/srv/browser/boot.py')");
  handle = py.globals.get("_b").get("handle");
}

onmessage = async (e) => {
  const m = e.data;
  if (m.type === "init") {
    ready = boot().then(() => postMessage({ type: "ready" }), (err) => postMessage({ type: "error", text: String(err && err.message || err).slice(0, 600) }));
    return;
  }
  if (m.type === "req") {
    await ready;
    try {
      const out = handle(m.method, m.url, py.toPy(m.headers), m.body ? m.body : null);
      const [status, headers, body] = out.toJs({ create_proxies: false });
      out.destroy();
      postMessage({ type: "res", id: m.id, status, headers, body });
    } catch (err) {
      postMessage({ type: "res", id: m.id, status: 500, headers: [["content-type", "application/json"]], body: new TextEncoder().encode(JSON.stringify({ detail: String(err).slice(0, 300) })) });
    }
  }
};
