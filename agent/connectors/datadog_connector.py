import os
import time
from datetime import datetime, timezone
from typing import List

import requests

from ..models import MetricPoint
from .base import BaseConnector


class DatadogConnector(BaseConnector):
    """
    Queries the Datadog metrics API (v1 /query) for each configured watch.

    Auth: API key + Application key, both scoped read-only where possible.
    """

    name = "datadog"

    def __init__(self, watches: list):
        self.api_key = os.getenv("DATADOG_API_KEY")
        self.app_key = os.getenv("DATADOG_APP_KEY")
        self.site = os.getenv("DATADOG_SITE", "datadoghq.com")
        self.watches = watches

    def is_configured(self) -> bool:
        return bool(self.api_key and self.app_key)

    def fetch(self, lookback_minutes: int) -> List[MetricPoint]:
        if not self.is_configured():
            return []
        points: List[MetricPoint] = []
        now = int(time.time())
        start = now - lookback_minutes * 60
        headers = {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
        }
        for w in self.watches:
            try:
                resp = requests.get(
                    f"https://api.{self.site}/api/v1/query",
                    headers=headers,
                    params={"from": start, "to": now, "query": w["query"]},
                    timeout=15,
                )
                resp.raise_for_status()
                series = resp.json().get("series", [])
                if not series or not series[0].get("pointlist"):
                    continue
                ts_ms, val = series[0]["pointlist"][-1]
                if val is None:
                    continue
                points.append(
                    MetricPoint(
                        source=self.name,
                        service=w["service"],
                        metric=w["metric"],
                        timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
                        value=float(val),
                        unit=w.get("unit", ""),
                    )
                )
            except Exception as e:
                print(f"[datadog] watch '{w.get('metric')}' failed: {e}")
        return points
