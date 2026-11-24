"""One command that checks the whole project: tests, build, evaluations, a live server with permission probes, and (optionally) real-browser flows.

    python check.py                 # tests + type check + build + evaluations + live server probes   (about 2 minutes)
    python check.py --quick         # tests + type check only                                          (about 40 seconds)
    python check.py --browser       # everything above + real-browser sweep and work flows (needs Playwright browsers, see docs/AI_TEST_GUIDE.md)
    python check.py --stage tests,sim        # only some stages: tests, web, evals, live, sim

Works on Windows, macOS and Linux. It never touches your data: the live check starts its own server on a free port with its own temporary
database, and stops it afterwards. Exit code 0 only if every stage that ran passed. A machine-readable report is written to check_report.json.
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
RESULTS: list[dict] = []


def sh(cmd, cwd=ROOT, env=None, timeout=900):
    e = {**os.environ, **(env or {})}
    t = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t
    except subprocess.TimeoutExpired as ex:
        return 124, f"timed out after {timeout}s\n{(ex.stdout or '')[-500:] if isinstance(ex.stdout, str) else ''}", time.time() - t
    except FileNotFoundError as ex:
        return 127, f"command not found: {ex}", time.time() - t


def record(name, status, detail="", secs=0.0, keep=1200):
    RESULTS.append({"stage": name, "status": status, "detail": detail.strip()[-keep:], "seconds": round(secs, 1)})
    icon = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "skip"}[status]
    first = detail.strip().splitlines()[0][:110] if detail.strip() else ""
    print(f"[{icon}] {name:<22} {secs:5.1f}s  {first}", flush=True)


def last(out, pat):
    import re
    m = re.findall(pat, out)
    return m[-1] if m else ""


def stage_env():
    t = time.time()
    py = sys.version_info
    node = shutil.which("node")
    nodev = sh([node, "--version"])[1].strip() if node else "not found"
    ok = py >= (3, 11)
    record("environment", "PASS" if ok else "FAIL", f"python {py.major}.{py.minor}.{py.micro}, node {nodev}, git {'yes' if shutil.which('git') else 'no'}, os {sys.platform}", time.time() - t)
    return ok


def stage_deps():
    code, out, secs = sh([sys.executable, "-c", "import fastapi, uvicorn, httpx, pydantic, pytest; print('imports ok')"])
    if code:
        record("python packages", "FAIL", "missing packages: run  pip install -r requirements.txt  (then  pip install pytest  if tests need it)", secs)
        return False
    record("python packages", "PASS", out, secs)
    return True


def stage_tests():
    # -rfs: list failed and skipped tests by name; --tb=short: the failing assertion, so a report alone is enough to diagnose
    code, out, secs = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfs", "--tb=short"], timeout=1200)
    line = last(out, r"(\d+ (?:passed|failed)[^\n]*)") or out[-300:]
    names = [l for l in out.splitlines() if l.startswith(("FAILED ", "ERROR ", "SKIPPED"))]
    detail = line
    if code != 0:
        body = out.split("=== FAILURES ===")[-1].split("=== short test summary")[0] if "=== FAILURES ===" in out else ""
        detail = line + "\n" + "\n".join(names) + ("\n\n" + body.strip()[-1800:] if body.strip() else "")
    elif names:
        detail = line + "\n" + "\n".join(names)
    record("tests", "PASS" if code == 0 else "FAIL", detail, secs, keep=3000)


def npm(*args, cwd=WEB, timeout=900):
    exe = shutil.which("npm")
    return sh([exe, *args], cwd=cwd, timeout=timeout) if exe else (127, "npm not found (install Node.js LTS)", 0.0)


def stage_web():
    if not shutil.which("node"):
        record("web type check", "SKIP", "Node.js not installed")
        record("web build", "SKIP", "Node.js not installed")
        return False
    if not (WEB / "node_modules").exists():
        code, out, secs = npm("install", "--no-audit", "--no-fund")
        if code:
            record("web install", "FAIL", out[-300:], secs)
            return False
        record("web install", "PASS", "npm install", secs)
    tsc = shutil.which("npx")
    code, out, secs = sh([tsc, "tsc", "--noEmit"], cwd=WEB)
    record("web type check", "PASS" if code == 0 else "FAIL", out or "no type errors", secs)
    code, out, secs = npm("run", "build")
    record("web build", "PASS" if code == 0 else "FAIL", last(out, r"(built in [^\n]+)") or out[-300:], secs)
    return code == 0


def stage_evals():
    env = {"LLM_PROVIDER": "mock"}
    for name, cmd in (("eval: documents", [sys.executable, "-m", "eval.run_eval", "--min-acc", "0.9"]),
                      ("eval: briefing", [sys.executable, "-m", "eval.briefing_eval", "--world"]),
                      ("eval: feedback replay", [sys.executable, "-m", "eval.feedback_eval"]),
                      ("eval: colleague replies", [sys.executable, "-m", "eval.npc_eval"])):
        code, out, secs = sh(cmd, env={**env, "MIN_RECALL": "0.8"})
        summary = last(out, r"(field_accuracy=[\d.]+)") or last(out, r"(recall=[\d.]+ precision=[\d.]+ injection_leaks=\d+)") or last(out, r'("todo_pass_rate": [\d.]+)') or last(out, r"(valid\s+\d+/\d+)")
        record(name, "PASS" if code == 0 else "FAIL", summary or out[-200:], secs)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LiveServer:
    """The combined server on a free port with a throw-away database inside its own temp directory (your own data is never touched)."""

    def __init__(self, sim=False):
        self.sim = sim

    def __enter__(self):
        self.tmp = tempfile.mkdtemp(prefix="nowhere-check-")
        self.port = free_port()
        env = {**os.environ, "TMP": self.tmp, "TEMP": self.tmp, "TMPDIR": self.tmp, "LLM_PROVIDER": "mock", "NPC_DELAY_SCALE": "0.5", "PORT": str(self.port), **({"NOWHERE_SIM": "1", "NPC_DELAY_SCALE": "0.2"} if self.sim else {})}
        for k in ("DOCFLOW_DB", "ASSISTANT_WEBHOOK_SECRET", "DOCFLOW_API_KEY", "WORLD_URL", "ASSISTANT_URL", "SEED_HISTORY"):
            env.pop(k, None)
        self.log = open(Path(self.tmp) / "server.log", "w", encoding="utf-8")
        self.p = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:combined", "--port", str(self.port)], cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self.base = f"http://127.0.0.1:{self.port}"
        for _ in range(60):
            try:
                if json.load(urllib.request.urlopen(self.base + "/api/health", timeout=2)).get("ok"):
                    return self
            except Exception:
                time.sleep(1)
        self.__exit__()
        raise RuntimeError("server did not start; see " + str(Path(self.tmp) / "server.log"))

    def __exit__(self, *a):
        try:
            self.p.terminate()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()
        self.log.close()
        shutil.rmtree(self.tmp, ignore_errors=True)


def stage_live(browser: bool, built: bool):
    try:
        srv = LiveServer().__enter__()
    except Exception as e:
        record("live server", "FAIL", str(e))
        return
    try:
        h = json.load(urllib.request.urlopen(srv.base + "/api/health"))
        record("live server", "PASS" if h.get("webhook_configured") else "FAIL", f"started on :{srv.port}, webhook secret auto-generated: {h.get('webhook_configured')}")
        code, out, secs = sh([sys.executable, "scripts/probes.py", srv.base])
        lat = " | ".join(l.replace("briefing latency ", "") for l in out.splitlines() if l.startswith("briefing latency"))
        record("permission probes", "PASS" if code == 0 else "FAIL", last(out, r"(\d+/\d+ probes as expected)") + (f"  [briefing: {lat}]" if lat else "") + ("" if code == 0 else "\n" + "\n".join(l for l in out.splitlines() if l.startswith("FAIL"))), secs)
        if not browser:
            record("browser sweep", "SKIP", "add --browser to run (needs Playwright browsers)")
            record("browser work flows", "SKIP", "add --browser to run")
            return
        if not built:
            record("browser sweep", "SKIP", "web app is not built (web/dist missing)")
            return
        node = shutil.which("node")
        have = sh([node, "-e", "require('playwright')"], cwd=WEB)[0] == 0
        if not have:
            record("browser sweep", "SKIP", "Playwright not installed: cd web && npm install && npx playwright install chromium")
            return
        for name, script in (("browser sweep", "e2e/sweep.cjs"), ("browser work flows", "e2e/flows.cjs"), ("browser slow-network DM", "e2e/dm-race.cjs")):
            code, out, secs = sh([node, script], cwd=WEB, env={"BASE_URL": srv.base + "/"}, timeout=900)
            line = last(out, r"(runs: \d+ \| runs with problems: \d+)") or last(out, r"(\d+/\d+ flow checks passed)") or last(out, r"(titles seen over time: .+)") or out[-250:]
            fails = [l for l in out.splitlines() if l.startswith(("FAIL", " !", "final title"))]
            tail = ""
            if code != 0:      # the server's own log usually says why (errors, slow calls)
                srv.log.flush()
                tail = "\n--- server log (last 20 lines) ---\n" + "\n".join((Path(srv.tmp) / "server.log").read_text(encoding="utf-8", errors="replace").splitlines()[-20:])
            record(name, "PASS" if code == 0 else "FAIL", line + ("\n" + "\n".join(fails[:6]) if fails else "") + tail, secs, keep=2500)
    finally:
        srv.__exit__()


def stage_sim():
    """Machinery of the one-week simulation (clock, schedule, answer key) with a rule-driven operator; the AI-judgement run is docs/WEEK_SIMULATION_PROMPT.md."""
    try:
        srv = LiveServer(sim=True).__enter__()
    except Exception as e:
        record("week simulation", "FAIL", str(e))
        return
    try:
        code, out, secs = sh([sys.executable, "scripts/sim_smoke.py", srv.base], timeout=900)
        record("week simulation", "PASS" if code == 0 else "FAIL", last(out, r"(week simulation machinery OK)") or out[-600:], secs)
    finally:
        srv.__exit__()


def main():
    ap = argparse.ArgumentParser(description="Project Nowhere: one-command project check")
    ap.add_argument("--quick", action="store_true", help="tests and type check only")
    ap.add_argument("--browser", action="store_true", help="also run real-browser sweep and work flows")
    ap.add_argument("--stage", default="", help="comma list: tests,web,evals,live,sim")
    a = ap.parse_args()
    want = set(filter(None, a.stage.split(",")))
    run = lambda s: (not want and (s in ("tests", "web") or not a.quick)) or s in want
    print(f"Project Nowhere check — {time.strftime('%Y-%m-%d %H:%M')}  ({sys.platform})\n")
    if not stage_env() or not stage_deps():
        print("\nFix the environment first (see the FAIL lines).")
        sys.exit(2)
    built = (WEB / "dist" / "index.html").exists()
    if run("tests"):
        stage_tests()
    if run("web"):
        built = stage_web() or built
    if run("evals"):
        stage_evals()
    if run("live"):
        stage_live(a.browser, built)
    if run("sim"):
        stage_sim()
    bad = [r for r in RESULTS if r["status"] == "FAIL"]
    skipped = [r["stage"] for r in RESULTS if r["status"] == "SKIP"]
    Path(ROOT / "check_report.json").write_text(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "platform": sys.platform, "results": RESULTS}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(RESULTS) - len(bad) - len(skipped)} passed, {len(bad)} failed, {len(skipped)} skipped   (report: check_report.json)")
    for r in bad:
        print(f"\n--- {r['stage']} ---\n{r['detail']}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
