import os
from datetime import datetime, timedelta, timezone
from typing import List

from ..models import MetricPoint
from .base import BaseConnector

try:
    import boto3
except ImportError:  # boto3 not installed -- connector will just report unconfigured
    boto3 = None


class CloudWatchConnector(BaseConnector):
    """
    Pulls the latest datapoint for each configured CloudWatch metric via get_metric_statistics.

    Auth: standard AWS credential chain (env vars, shared config, or instance role).
    """

    name = "cloudwatch"

    def __init__(self, watches: list):
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.watches = watches
        self._client = None

    def is_configured(self) -> bool:
        if boto3 is None:
            return False
        return bool(os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE") or os.getenv("AWS_ROLE_ARN"))

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client("cloudwatch", region_name=self.region)
        return self._client

    def fetch(self, lookback_minutes: int) -> List[MetricPoint]:
        if not self.is_configured():
            return []
        points: List[MetricPoint] = []
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=lookback_minutes)
        for w in self.watches:
            stat = w.get("statistic", "Average")
            try:
                resp = self.client.get_metric_statistics(
                    Namespace=w["namespace"],
                    MetricName=w["metric_name"],
                    Dimensions=w.get("dimensions", []),
                    StartTime=start,
                    EndTime=end,
                    Period=w.get("period", 60),
                    Statistics=[stat],
                )
                datapoints = sorted(resp.get("Datapoints", []), key=lambda d: d["Timestamp"])
                if not datapoints:
                    continue
                latest = datapoints[-1]
                points.append(
                    MetricPoint(
                        source=self.name,
                        service=w["service"],
                        metric=w["metric"],
                        timestamp=latest["Timestamp"],
                        value=float(latest[stat]),
                        unit=latest.get("Unit", ""),
                    )
                )
            except Exception as e:
                print(f"[cloudwatch] watch '{w.get('metric')}' failed: {e}")
        return points
