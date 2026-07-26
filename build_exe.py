import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "monitor_agent.spec"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> None:
    for path in [DIST, BUILD, SPEC]:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    run([
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "monitor-agent",
        "--add-data",
        "dashboard/static;dashboard/static",
        "--add-data",
        "config.yaml;.",
        "--collect-submodules",
        "dashboard",
        "--collect-submodules",
        "agents",
        "--hidden-import",
        "dashboard.server",
        "--hidden-import",
        "agents.cloudwatch_agent.server",
        "--hidden-import",
        "agents.prometheus_agent.server",
        "run_all.py",
    ])

    print("\nBuilt executable:")
    exe = DIST / "monitor-agent.exe"
    print(exe)


if __name__ == "__main__":
    main()
