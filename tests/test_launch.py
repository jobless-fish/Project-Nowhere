import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import launch

ROOT = Path(__file__).parent.parent
needs_dist = __import__("pytest").mark.skipif(not (ROOT / "web" / "dist" / "index.html").exists(), reason="web/dist not built")


def port_open(p):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", p)) == 0


def test_browser_discovery(tmp_path, monkeypatch):
    fake = tmp_path / "chromium"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert launch.find_browser({}, "linux") == str(fake)                                     # found on PATH
    assert launch.find_browser({"NOWHERE_BROWSER": str(fake)}, "linux") == str(fake)         # explicit choice wins
    assert launch.find_browser({"NOWHERE_BROWSER": "/no/such/browser"}, "linux") is None     # a wrong explicit choice is not silently ignored
    monkeypatch.setenv("PATH", "")
    assert launch.find_browser({}, "linux") is None                                          # nothing installed -> caller falls back to the default browser


def test_app_window_command_has_no_browser_chrome_and_its_own_profile():
    cmd = launch.app_command("/x/chrome", "http://127.0.0.1:8000", "/tmp/prof", {})
    assert cmd[0] == "/x/chrome" and "--app=http://127.0.0.1:8000" in cmd and "--user-data-dir=/tmp/prof" in cmd
    assert launch.app_command("/x", "http://u", "/p", {"NOWHERE_BROWSER_ARGS": "--foo {url}"}) == ["/x", "--foo", "http://u"]


def test_pick_port_prefers_the_default_then_falls_back():
    free = launch.pick_port(0)
    assert launch.pick_port(free) == free
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        busy = s.getsockname()[1]
        s.listen()
        assert launch.pick_port(busy) not in (busy, 0)                                       # taken -> any free port instead of crashing


@needs_dist
def test_closing_the_window_stops_the_server():
    """Full lifecycle with a stand-in 'browser' that stays open 5 s and then exits, as when a user closes the window."""
    port = launch.pick_port(0)
    env = {**os.environ, "NOWHERE_BROWSER": sys.executable, "NOWHERE_BROWSER_ARGS": "-c 'import time; time.sleep(5)'", "PYTHONPATH": str(ROOT)}
    p = subprocess.Popen([sys.executable, "launch.py", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(80):
        if port_open(port):
            break
        time.sleep(0.25)
    assert urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3).status == 200      # server is up while the "window" is open
    assert p.wait(timeout=30) == 0
    time.sleep(0.5)
    assert not port_open(port), "server was left running after the window closed"


def test_missing_screen_build_gives_a_clear_message(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "ROOT", tmp_path)
    assert launch.main(["--no-browser"]) == 2


@needs_dist
def test_terminal_close_or_kill_does_not_leave_the_server_running():
    """Regression: SIGTERM/SIGHUP used to kill only the launcher and orphan the server."""
    import signal
    import pytest
    if not hasattr(signal, "SIGHUP"):
        pytest.skip("POSIX signals only")
    for sig in (signal.SIGTERM, signal.SIGHUP):
        port = launch.pick_port(0)
        p = subprocess.Popen([sys.executable, "launch.py", "--no-browser", "--port", str(port)], cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)},
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(80):
            if port_open(port):
                break
            time.sleep(0.25)
        assert port_open(port)
        p.send_signal(sig)
        assert p.wait(timeout=20) == 0
        time.sleep(0.5)
        assert not port_open(port), f"server orphaned after {sig.name}"


def test_light_is_the_default_theme_and_dark_is_opt_in():
    """The built stylesheet must not switch to dark just because the OS is dark."""
    css = (ROOT / "web" / "src" / "styles.css").read_text(encoding="utf-8")
    assert ":root:not([data-theme=\"light\"])" not in css                         # the old 'follow the OS unless told otherwise' rule is gone
    assert 'data-theme="auto"' in css and 'data-theme="dark"' in css
    head = css.split("@media (prefers-color-scheme: dark)")[0]
    assert "--bg: #f9f5ea" in head and "color-scheme: light" in head                # default tokens are the cream light ones
    assert 't==="dark"||t==="auto"' in (ROOT / "web" / "index.html").read_text(encoding="utf-8")
