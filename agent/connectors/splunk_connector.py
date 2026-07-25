import os
from datetime import datetime, timezone
from typing import List

import requests

from ..models import MetricPoint
from .base import BaseConnector


class SplunkConnector(BaseConnector):
    """
    Runs configured SPL searches against the Splunk REST API (oneshot mode)
    and extracts a single numeric value from each result.

    Auth: Splunk HEC/auth token via SPLUNK_TOKEN (Bearer token auth).
    Each "watch" in config.yaml maps one SPL search to a (service, metric) pair.
    """

    name = "splunk"

    def __init__(self, watches: list):
        self.host = os.getenv("SPLUNK_HOST")
        self.port = os.getenv("SPLUNK_PORT", "8089")
        self.token = os.getenv("SPLUNK_TOKEN")
        self.verify_ssl = os.getenv("SPLUNK_VERIFY_SSL", "true").lower() == "true"
        self.watches = watches

    def is_configured(self) -> bool:
        return bool(self.host and self.token)

    def _run_oneshot(self, spl: str, earliest: str) -> dict:
        url = f"https://{self.host}:{self.port}/services/search/jobs"
        headers = {"Authorization": f"Bearer {self.token}"}
        search = spl.strip()
        if not (search.startswith("search") or search.startswith("|")):
            search = f"search {search}"
        data = {
            "search": search,
            "earliest_time": earliest,
            "latest_time": "now",
            "exec_mode": "oneshot",
            "output_mode": "json",
        }
        resp = requests.post(url, headers=headers, data=data, verify=self.verify_ssl, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, lookback_minutes: int) -> List[MetricPoint]:
        if not self.is_configured():
            return []
        points: List[MetricPoint] = []
        earliest = f"-{lookback_minutes}m"
        for w in self.watches:
            try:
                result = self._run_oneshot(w["spl"], earliest)
                rows = result.get("results", [])
                if not rows:
                    continue
                value = float(rows[0].get(w["value_field"], 0))
                points.append(
                    MetricPoint(
                        source=self.name,
                        service=w["service"],
                        metric=w["metric"],
                        timestamp=datetime.now(timezone.utc),
                        value=value,
                        unit=w.get("unit", ""),
                    )
                )
            except Exception as e:
                print(f"[splunk] watch '{w.get('metric')}' failed: {e}")
        return points
