"""BaseConnector implementation that fetches MetricPoints from an A2A sub-agent.

The master agent adds one A2AConnector per running sub-agent. Each connector:
  1. Pings /health to decide whether to participate in the current poll cycle.
  2. POSTs a task to /tasks/send carrying {"lookback_minutes": N}.
  3. Deserializes the JSON artifact in the response back into MetricPoint objects.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

import httpx

from agent.connectors.base import BaseConnector
from agent.models import MetricPoint
from agents.master_agent.a2a_client import A2AClient

log = logging.getLogger("a2a-connector")


class A2AConnector(BaseConnector):
    """Fetches MetricPoints from a remote A2A sub-agent over HTTP."""

    def __init__(self, agent_url: str, source_name: str) -> None:
        """
        Args:
            agent_url:   Base URL of the sub-agent (e.g. http://localhost:8001).
            source_name: Human-readable label used in logs (e.g. "cloudwatch-a2a").
        """
        self.agent_url: str = agent_url.rstrip("/")
        self.name: str = source_name
        self._client: A2AClient = A2AClient()
        self._reachable: Optional[bool] = None  # cached per-poll

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        """Ping /health; return False (and warn) if the sub-agent is unreachable."""
        try:
            resp = httpx.get(f"{self.agent_url}/health", timeout=3.0)
            self._reachable = resp.status_code == 200
        except Exception:  # noqa: BLE001
            self._reachable = False

        if not self._reachable:
            log.warning(f"[{self.name}] sub-agent unreachable at {self.agent_url} — skipping")
        return bool(self._reachable)

    def fetch(self, lookback_minutes: int) -> List[MetricPoint]:
        """Send an A2A task and deserialize the returned MetricPoint JSON."""
        response = self._client.send_task(
            self.agent_url,
            {"lookback_minutes": lookback_minutes},
        )
        return self._parse_response(response)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_response(self, response: dict) -> List[MetricPoint]:
        points: List[MetricPoint] = []
        try:
            artifacts = response.get("artifacts", [])
            if not artifacts:
                log.warning(f"[{self.name}] A2A response contained no artifacts")
                return points
            text = artifacts[0]["parts"][0]["text"]
            data: list = json.loads(text)
            for item in data:
                points.append(MetricPoint(
                    source=item["source"],
                    service=item["service"],
                    metric=item["metric"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    value=float(item["value"]),
                    unit=item.get("unit", ""),
                ))
        except (KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
            log.warning(f"[{self.name}] failed to parse A2A response: {exc}")
        return points
