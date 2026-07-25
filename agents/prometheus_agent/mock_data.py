"""Mock Prometheus metric data generator.

Generates realistic MetricPoint data for three Prometheus-instrumented services:
  - payment-service  → http_request_duration_ms  (p95 latency)
  - auth-service     → http_request_duration_ms  (p95 latency)
  - k8s-node-1       → node_cpu_usage_percent

Anomaly injection strategy
--------------------------
Uses the same 5-minute bucket seed as the CloudWatch agent so both sources
fire anomalies in the same polling cycle. The Prometheus spike lands one minute
later than the CloudWatch spike (ANOMALY_OFFSET_FROM_END = 1), keeping them
within the 5-minute lag window so the master's Correlator groups them into
one Incident.
"""

import random
import time
from datetime import datetime, timedelta
from typing import List

from agent.models import MetricPoint

# (service, metric, normal_mean, normal_std, unit, spike_value)
_METRICS = [
    ("payment-service", "http_request_duration_ms", 150.0, 25.0, "ms",      950.0),
    ("auth-service",    "http_request_duration_ms",  95.0, 18.0, "ms",      720.0),
    ("k8s-node-1",      "node_cpu_usage_percent",    52.0,  9.0, "%",        88.0),
]

# One minute closer to "now" than the CloudWatch anomaly offset of 2,
# so they fall within the same lag window and get correlated.
_ANOMALY_OFFSET_FROM_END = 1


def generate_prometheus_metrics(lookback_minutes: int) -> List[MetricPoint]:
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
        metric_rng = random.Random(bucket ^ hash(metric))
        for i in range(lookback_minutes):
            ts = now - timedelta(minutes=lookback_minutes - i)
            if has_anomaly and i == anomaly_idx:
                value = spike_val + metric_rng.gauss(0, spike_val * 0.04)
            else:
                value = max(0.0, metric_rng.gauss(mean, std))
            points.append(MetricPoint(
                source="prometheus",
                service=service,
                metric=metric,
                timestamp=ts,
                value=round(value, 2),
                unit=unit,
            ))
    return points
