"""Prometheus A2A sub-agent server.

Exposes three endpoints:
  GET  /.well-known/agent.json  — A2A AgentCard (discovery)
  GET  /health                  — Liveness check
  POST /tasks/send              — A2A task endpoint; returns mock Prometheus MetricPoints

Run:
    python -m agents.prometheus_agent.server
"""

import json
import logging

import uvicorn
from fastapi import FastAPI

from agents.a2a_schema import (
    AgentCard,
    AgentSkill,
    Artifact,
    TaskResponse,
    TaskSendRequest,
    TaskStatus,
    TextPart,
)
from agents.prometheus_agent.mock_data import generate_prometheus_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("prometheus-agent")

PORT = 8002

app = FastAPI(title="Prometheus A2A Agent", version="1.0.0")

_AGENT_CARD = AgentCard(
    name="Prometheus Monitoring Agent",
    description=(
        "Provides mock Prometheus metrics for payment-service and auth-service "
        "(HTTP p95 latency) and k8s-node-1 (CPU usage)."
    ),
    version="1.0.0",
    url=f"http://localhost:{PORT}",
    skills=[
        AgentSkill(
            id="fetch_metrics",
            name="Fetch Prometheus Metrics",
            description=(
                "Returns MetricPoint data for the requested lookback window. "
                "Input: JSON text with key 'lookback_minutes' (int). "
                "Output: JSON array of serialized MetricPoint objects."
            ),
        )
    ],
)


@app.get("/.well-known/agent.json", summary="A2A Agent Card")
async def agent_card() -> dict:
    return _AGENT_CARD.model_dump()


@app.get("/health", summary="Liveness check")
async def health() -> dict:
    return {"status": "ok", "agent": "prometheus"}


@app.post("/tasks/send", summary="Execute a monitoring task")
async def tasks_send(request: TaskSendRequest) -> dict:
    log.info(f"task id={request.id} received")

    try:
        payload = json.loads(request.message.parts[0].text)
        lookback_minutes = int(payload.get("lookback_minutes", 15))
    except (json.JSONDecodeError, IndexError, ValueError, AttributeError):
        lookback_minutes = 15

    points = generate_prometheus_metrics(lookback_minutes)
    log.info(f"returning {len(points)} metric points for lookback={lookback_minutes}m")

    points_json = json.dumps([
        {
            "source": p.source,
            "service": p.service,
            "metric": p.metric,
            "timestamp": p.timestamp.isoformat(),
            "value": p.value,
            "unit": p.unit,
        }
        for p in points
    ])

    return TaskResponse(
        id=request.id,
        status=TaskStatus(state="completed"),
        artifacts=[Artifact(name="metrics", parts=[TextPart(text=points_json)])],
    ).model_dump()


if __name__ == "__main__":
    uvicorn.run("agents.prometheus_agent.server:app", host="0.0.0.0", port=PORT, log_level="info")
