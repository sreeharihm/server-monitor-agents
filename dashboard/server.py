"""Dashboard server — serves the incident monitoring UI and REST API.

Endpoints:
  GET  /                      → Dashboard HTML page
  GET  /api/incidents         → All incidents (newest first), supports ?limit=N
  GET  /api/incidents/{id}    → Single incident detail
  GET  /api/stats             → Aggregated summary stats
  GET  /health                → Liveness check

Run standalone:
    python -m dashboard.server

Or via run_all.py (port 8000).
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("dashboard")

PORT = 8000

_THIS_DIR = Path(__file__).parent


def _resolve_runtime_path(*parts: str) -> Path:
    relative_path = Path(*parts)
    if getattr(sys, "frozen", False):
        candidates = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / relative_path)
        candidates.append(Path(sys.executable).resolve().parent / relative_path)
        candidates.append(Path.cwd() / relative_path)
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return Path(sys.executable).resolve().parent / relative_path
    return _THIS_DIR.parent / relative_path


_INCIDENTS_DIR = _resolve_runtime_path("output", "incidents")
_INDEX_HTML = _THIS_DIR / "static" / "index.html"

app = FastAPI(title="Monitor Agent Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_incidents() -> List[Dict[str, Any]]:
    """Read all incident JSON files and return them sorted newest-first."""
    incidents: List[Dict[str, Any]] = []
    if not _INCIDENTS_DIR.exists():
        return incidents
    for path in _INCIDENTS_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                incidents.append(json.load(f))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning(f"could not read {path.name}: {exc}")
    incidents.sort(key=lambda i: i.get("created_at", ""), reverse=True)
    return incidents


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": "dashboard"}


@app.get("/")
async def index() -> FileResponse:
    if not _INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(_INDEX_HTML, media_type="text/html")


@app.get("/api/stats")
async def stats() -> dict:
    incidents = _load_incidents()
    total = len(incidents)
    critical_count = 0
    warning_count = 0
    services: set = set()

    for inc in incidents:
        for a in inc.get("anomalies", []):
            sev = a.get("severity", "")
            if sev == "critical":
                critical_count += 1
            elif sev == "warning":
                warning_count += 1
            services.add(f"{a.get('source','?')}:{a.get('service','?')}")

    return {
        "total_incidents": total,
        "critical_anomalies": critical_count,
        "warning_anomalies": warning_count,
        "affected_services": len(services),
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/api/incidents")
async def list_incidents(limit: Optional[int] = None) -> List[dict]:
    incidents = _load_incidents()
    if limit is not None and limit > 0:
        incidents = incidents[:limit]
    return incidents


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict:
    path = _INCIDENTS_DIR / f"{incident_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("dashboard.server:app", host="0.0.0.0", port=PORT, log_level="info")
