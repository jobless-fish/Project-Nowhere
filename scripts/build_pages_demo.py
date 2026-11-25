"""Builds the in-browser demo into site/demo/ (what GitHub Pages serves under /demo/).

    python scripts/build_pages_demo.py            # needs node (web build) and pip (two pure-python wheels)

Output (not committed): site/demo/{index.html, assets/, worker.js, nowhere-py.zip, wheels/}. The Python runtime itself (Pyodide 0.27.7 and
pydantic, anyio, httpx, ...) is fetched by the page from the official jsdelivr CDN at run time.
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "demo"
WHEELS = ["fastapi==0.115.6", "starlette==0.41.3"]


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    env = {**__import__("os").environ, "VITE_STATIC": "1"}
    subprocess.run(["npm", "run", "build", "--", "--outDir", str(OUT), "--emptyOutDir"], cwd=ROOT / "web", env=env, check=True,
                   shell=sys.platform == "win32")
    shutil.copy(ROOT / "browser" / "worker.js", OUT / "worker.js")
    with zipfile.ZipFile(OUT / "nowhere-py.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for d in ("app", "world", "eval"):
            for f in sorted((ROOT / d).rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                    z.write(f, f.relative_to(ROOT))
        z.write(ROOT / "simclock.py", "simclock.py")
        z.write(ROOT / "browser" / "asgi_sync.py", "browser/asgi_sync.py")
        z.write(ROOT / "browser" / "boot.py", "browser/boot.py")
    (OUT / "wheels").mkdir()
    subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps", "-q", "-d", str(OUT / "wheels"), *WHEELS], check=True)
    print("built", OUT, f"({sum(f.stat().st_size for f in OUT.rglob('*') if f.is_file()) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
