"""Start the simulation server for the one-week operating simulation (docs/WEEK_SIMULATION_PROMPT.md).

    python scripts/sim_server.py [--port 8890] [--llm]

NOWHERE_SIM=1 turns on the simulated clock endpoints (/world/sim/*). The server gets its own temporary database (your real data is untouched) and a
fresh random webhook secret; replies from colleagues arrive quickly (NPC_DELAY_SCALE=0.2). By default the built-in mock model is used (no key, no cost);
--llm keeps whatever LLM_PROVIDER/LLM_* variables you have set. Stop with Ctrl+C: the temporary database is deleted.
"""
import argparse
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8890)
    ap.add_argument("--llm", action="store_true", help="use the LLM configured in the environment instead of the mock model")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="nowhere-sim-")
    atexit.register(shutil.rmtree, tmp, True)
    for k in ("TMP", "TEMP", "TMPDIR"):
        os.environ[k] = tmp
    for k in ("DOCFLOW_DB", "ASSISTANT_WEBHOOK_SECRET", "WORLD_URL", "ASSISTANT_URL", "DOCFLOW_API_KEY"):
        os.environ.pop(k, None)
    os.environ.update(NOWHERE_SIM="1", NPC_DELAY_SCALE="0.2", PORT=str(a.port))
    if not a.llm:
        os.environ["LLM_PROVIDER"] = "mock"
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    print(f"Simulation server: http://127.0.0.1:{a.port}   (state: GET /world/sim/state, start: POST /world/sim/start)", flush=True)
    import uvicorn
    uvicorn.run("server:combined", host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
