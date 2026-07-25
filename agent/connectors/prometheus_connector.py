import os
from datetime import datetime, timezone
from typing import List

import requests

from ..models import MetricPoint
from .base import BaseConnector


class PrometheusConnector(BaseConnector):
    """
    Runs configured PromQL instant queries against the Prometheus HTTP API.

    Auth: none by default. If your Prometheus sits behind a reverse proxy with
    basic auth or a bearer token, add headers in _query() as needed.
    """

    name = "prometheus"

    def __init__(self, watches: list):
        self.base_url = os.getenv("PROMETHEUS_URL")
        self.watches = watches

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def fetch(self, lookback_minutes: int) -> List[MetricPoint]:
        if not self.is_configured():
            return []
        points: List[MetricPoint] = []
        for w in self.watches:
            try:
                resp = requests.get(
                    f"{self.base_url}/api/v1/query",
                    params={"query": w["promql"]},
                    timeout=15,
                )
                resp.raise_for_status()
                result = resp.json().get("data", {}).get("result", [])
                if not result:
                    continue
                ts, val = result[0]["value"]
                points.append(
                    MetricPoint(
                        source=self.name,
                        service=w["service"],
                        metric=w["metric"],
                        timestamp=datetime.fromtimestamp(float(ts), tz=timezone.utc),
                        value=float(val),
                        unit=w.get("unit", ""),
                    )
                )
            except Exception as e:
                print(f"[prometheus] watch '{w.get('metric')}' failed: {e}")
        return points
