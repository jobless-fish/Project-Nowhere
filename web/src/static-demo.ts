// GitHub Pages build: there is no server. The product (company systems + assistant) runs in a Web Worker as Python (Pyodide) and this
// replaces window.fetch for /api and /world so the app itself is unchanged. Nothing leaves the tab; data is gone on reload.
type Pending = { resolve: (r: Response) => void };
const pending = new Map<number, Pending>();
let worker: Worker | null = null;
let n = 0;

export function startStaticDemo(onProgress: (t: string) => void): Promise<void> {
  const real = window.fetch.bind(window);
  const params = new URLSearchParams(location.search);
  const py = params.get("py");   // test hook: serve the Python runtime from another folder instead of the CDN
  worker = new Worker(`./worker.js${py ? `?py=${encodeURIComponent(py)}` : ""}`);
  return new Promise((resolve, reject) => {
    worker!.onmessage = (e) => {
      const m = e.data;
      if (m.type === "progress") onProgress(m.text);
      else if (m.type === "ready") resolve();
      else if (m.type === "error") reject(new Error(m.text));
      else if (m.type === "res") {
        const p = pending.get(m.id); pending.delete(m.id);
        p?.resolve(new Response(m.status === 204 ? null : m.body, { status: m.status, headers: m.headers }));
      }
    };
    worker!.postMessage({ type: "init" });
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.pathname + input.search : input.url;
      const path = url.replace(/^https?:\/\/[^/]+/, "");
      if (!(path.startsWith("/api/") || path.startsWith("/world/"))) return real(input, init);
      const headers: Record<string, string> = {};
      new Headers(init?.headers).forEach((v, k) => { headers[k] = v; });
      const body = typeof init?.body === "string" ? init.body : null;
      return new Promise<Response>((res) => {
        const id = ++n; pending.set(id, { resolve: res });
        worker!.postMessage({ type: "req", id, method: init?.method || "GET", url: path, headers, body });
      });
    };
  });
}
