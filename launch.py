#!/usr/bin/env python3
"""Open Nowhere in its own window (no tabs, no address bar), like a desktop app.

    python launch.py                    start the server, open an app window; closing the window stops the server
    python launch.py --port 9000        pick the port (default: 8000 if free, otherwise any free port)
    python launch.py --default-browser  open a normal browser tab instead of an app window
    python launch.py --no-browser       server only

It reuses the Chrome / Edge / Brave / Chromium already on your computer (no extra packages). Set NOWHERE_BROWSER to a browser
executable to choose one yourself. Build the screen once first:  cd web && npm install && npx vite build
"""
import argparse
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
WINDOWS = [r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe", r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
           r"%ProgramFiles%\Google\Chrome\Application\chrome.exe", r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
           r"%LocalAppData%\Google\Chrome\Application\chrome.exe", r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"]
MAC = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
       "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser", "/Applications/Chromium.app/Contents/MacOS/Chromium"]
LINUX = ["google-chrome", "google-chrome-stable", "microsoft-edge", "microsoft-edge-stable", "brave-browser", "chromium", "chromium-browser"]


def find_browser(env=None, platform=None):
    env, platform = os.environ if env is None else env, sys.platform if platform is None else platform
    forced = env.get("NOWHERE_BROWSER")
    if forced:
        return forced if Path(forced).exists() or shutil.which(forced) else None
    if platform.startswith("win"):
        for c in WINDOWS:
            path = os.path.expandvars(c)
            if "%" not in path and Path(path).exists():
                return path
    elif platform == "darwin":
        for c in MAC:
            if Path(c).exists():
                return c
    for name in LINUX:
        found = shutil.which(name)
        if found:
            return found
    return None


def app_command(exe, url, profile, env=None):
    """A separate profile makes the browser start its own process, so we can tell when the window is closed."""
    env = os.environ if env is None else env
    if env.get("NOWHERE_BROWSER_ARGS"):          # test hook: replaces the default arguments; {url} is substituted
        return [exe, *[a.replace("{url}", url) for a in shlex.split(env["NOWHERE_BROWSER_ARGS"])]]
    return [exe, f"--app={url}", f"--user-data-dir={profile}", "--window-size=1360,900", "--no-first-run", "--no-default-browser-check", "--disable-extensions"]


def pick_port(preferred=8000):
    for port in (preferred, 0) if preferred else (0,):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("no free port")


def wait_ready(url, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if urllib.request.urlopen(url + "/api/health", timeout=1).status == 200:
                return True
        except Exception:
            time.sleep(0.25)
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Open Nowhere in its own window.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true", help="server only")
    ap.add_argument("--default-browser", action="store_true", help="open a normal browser tab instead of an app window")
    a = ap.parse_args(argv)
    if not (ROOT / "web" / "dist" / "index.html").exists():
        print("화면이 아직 빌드되지 않았어요. 먼저 한 번만 실행해 주세요:\n  cd web && npm install && npx vite build", file=sys.stderr)
        return 2
    def _stop(*_):          # closing the terminal (SIGHUP) or `kill` (SIGTERM) must not leave the server running in the background
        raise KeyboardInterrupt
    for name in ("SIGTERM", "SIGHUP", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _stop)
    port = pick_port(a.port)
    url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:combined", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"], cwd=ROOT)
    profile = tempfile.mkdtemp(prefix="nowhere-window-")
    try:
        if not wait_ready(url):
            print("서버가 시작되지 않았어요. 위의 오류 메시지를 확인해 주세요.", file=sys.stderr)
            return 1
        print(f"노웨어가 {url} 에서 실행 중이에요.")
        exe = None if (a.no_browser or a.default_browser) else find_browser()
        if a.no_browser:
            print("서버만 실행 중이에요. 끝내려면 Ctrl+C를 누르세요.")
            server.wait()
        elif exe is None:
            if not a.default_browser:
                print("Chrome, Edge, Brave, Chromium을 찾지 못해 기본 브라우저로 열어요. (NOWHERE_BROWSER로 직접 지정할 수 있어요)")
            webbrowser.open(url)
            print("끝내려면 이 창에서 Ctrl+C를 누르세요.")
            server.wait()
        else:
            started = time.time()
            win = subprocess.Popen(app_command(exe, url, profile))
            win.wait()                                   # returns when the window is closed
            if time.time() - started < 3:                # the browser handed the window to an already running instance
                print("창이 바로 닫혔어요. 이미 켜진 브라우저가 창을 대신 열었을 수 있어요. 서버는 계속 실행 중이에요. 끝내려면 Ctrl+C를 누르세요.")
                server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.terminate()
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()
        shutil.rmtree(profile, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
