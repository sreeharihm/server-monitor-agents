"""Mock AWS CloudWatch metric data generator.

Generates realistic MetricPoint data for three CloudWatch-backed resources:
  - web-api         → EC2 CPUUtilization
  - order-db        → RDS DatabaseConnections
  - load-balancer   → ALB HTTPCode_ELB_5XX_Count

Anomaly injection strategy
--------------------------
A deterministic seed derived from the current 5-minute time bucket
controls whether this cycle has an anomaly (≈15% of buckets will fire).
When active, a spike is injected at the second-to-last data point so the
detector sees a full rolling baseline before the outlier appears.

Both cloudwatch_agent and prometheus_agent share the same bucket-seed logic,
so their spikes land within the same polling cycle and get correlated by the
master agent's Correlator into one Incident.
"""

import random
import time
from datetime import datetime, timedelta
from typing import List

from agent.models import MetricPoint

# (service, metric, normal_mean, normal_std, unit, spike_value)
_METRICS = [
    ("web-api",       "cpu_utilization_pct",  35.0,  8.0, "%",     92.0),
    ("order-db",      "database_connections", 28.0,  5.0, "Count", 118.0),
    ("load-balancer", "http_5xx_count",         2.0,  1.0, "Count",  82.0),
]

# Anomaly appears at this many minutes before the end of the lookback window.
_ANOMALY_OFFSET_FROM_END = 2


def generate_cloudwatch_metrics(lookback_minutes: int) -> List[MetricPoint]:
    """Return one MetricPoint per minute per metric over the lookback window.

    Args:
        lookback_minutes: How many minutes of history to generate.

    Returns:
        A list of MetricPoint objects ordered oldest → newest.
    """
    now = datetime.utcnow().replace(second=0, microsecond=0)

    # Shared anomaly decision across agents (same 5-min bucket seed)
    bucket = int(time.time() / 300)
    shared_rng = random.Random(bucket)
    has_anomaly = shared_rng.random() < 0.15

    anomaly_idx = lookback_minutes - _ANOMALY_OFFSET_FROM_END

    points: List[MetricPoint] = []
    for service, metric, mean, std, unit, spike_val in _METRICS:
        # Per-metric RNG for independent value variation
        metric_rng = random.Random(bucket ^ hash(metric))
        for i in range(lookback_minutes):
            ts = now - timedelta(minutes=lookback_minutes - i)
            if has_anomaly and i == anomaly_idx:
                value = spike_val + metric_rng.gauss(0, spike_val * 0.04)
            else:
                value = max(0.0, metric_rng.gauss(mean, std))
            points.append(MetricPoint(
                source="cloudwatch",
                service=service,
                metric=metric,
                timestamp=ts,
                value=round(value, 2),
                unit=unit,
            ))
    return points
