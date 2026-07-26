"""run_all.py — Start all A2A sub-agents then the master monitoring agent.

Usage:
    python run_all.py

What it does:
  1. Launches cloudwatch-agent (port 8001) and prometheus-agent (port 8002)
     as child processes.
  2. Polls each agent's /health endpoint until it responds (up to 15 seconds).
  3. Starts main.py (the master monitoring agent) once both sub-agents are ready.
  4. On Ctrl+C, shuts everything down cleanly.
"""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run-all")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

_SUB_AGENTS = [
    {
        "name": "dashboard",
        "module": "dashboard.server",
        "port": 8000,
    },
    {
        "name": "cloudwatch-agent",
        "module": "agents.cloudwatch_agent.server",
        "port": 8001,
    },
    {
        "name": "prometheus-agent",
        "module": "agents.prometheus_agent.server",
        "port": 8002,
    },
]

_HEALTH_RETRIES = 15
_HEALTH_DELAY = 1.0  # seconds between retries


def _wait_for_health(name: str, port: int) -> bool:
    url = f"http://localhost:{port}/health"
    for attempt in range(1, _HEALTH_RETRIES + 1):
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                log.info(f"[{name}] ready (port {port})")
                return True
        except Exception:
            pass
        log.info(f"[{name}] waiting for health check... ({attempt}/{_HEALTH_RETRIES})")
        time.sleep(_HEALTH_DELAY)
    log.error(f"[{name}] did not become healthy after {_HEALTH_RETRIES} attempts")
    return False


def _build_component_command(name: str, module: str | None = None) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--mode", name]
    if module is None:
        return [sys.executable, str(ROOT / "main.py")]
    return [sys.executable, str(ROOT / "run_all.py"), "--mode", name]


def _run_component(mode: str) -> None:
    if mode == "dashboard":
        import uvicorn

        uvicorn.run("dashboard.server:app", host="0.0.0.0", port=8000, log_level="info")
    elif mode == "cloudwatch-agent":
        import uvicorn

        uvicorn.run("agents.cloudwatch_agent.server:app", host="0.0.0.0", port=8001, log_level="info")
    elif mode == "prometheus-agent":
        import uvicorn

        uvicorn.run("agents.prometheus_agent.server:app", host="0.0.0.0", port=8002, log_level="info")
    elif mode == "master":
        from main import main as run_master

        run_master()
    else:
        raise ValueError(f"unsupported mode: {mode}")


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--mode":
        _run_component(sys.argv[2])
        return

    procs: list = []

    def _shutdown(sig, frame):  # noqa: ANN001
        log.info("shutting down all agents...")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    try:
        signal.signal(signal.SIGTERM, _shutdown)
    except (OSError, AttributeError):
        pass  # SIGTERM unavailable on some platforms (e.g. Windows)

    # ------------------------------------------------------------------ #
    # 1. Start sub-agent servers                                           #
    # ------------------------------------------------------------------ #
    for agent in _SUB_AGENTS:
        log.info(f"starting {agent['name']} on port {agent['port']}...")
        p = subprocess.Popen(
            _build_component_command(agent["name"], agent["module"]),
            # Inherit stdout/stderr so sub-agent logs appear in this terminal.
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        procs.append(p)

    # ------------------------------------------------------------------ #
    # 2. Wait for all sub-agents to be healthy                             #
    # ------------------------------------------------------------------ #
    all_ready = all(_wait_for_health(a["name"], a["port"]) for a in _SUB_AGENTS)
    if not all_ready:
        log.error("one or more sub-agents failed to start — aborting")
        for p in procs:
            p.terminate()
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # 3. Start the master monitoring agent (blocking)                      #
    # ------------------------------------------------------------------ #
    log.info("all sub-agents ready — starting master agent (main.py)...")
    log.info("dashboard available at http://localhost:8000")
    master = subprocess.Popen(
        _build_component_command("master"),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    procs.append(master)
    master.wait()


if __name__ == "__main__":
    main()
