from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class MetricPoint:
    """A single metric reading pulled from a monitoring source."""
    source: str      # 'splunk' | 'cloudwatch' | 'prometheus' | 'datadog'
    service: str      # logical service/host name, e.g. 'payment-api'
    metric: str       # metric name, e.g. 'error_rate_pct'
    timestamp: datetime
    value: float
    unit: str = ""


@dataclass
class Anomaly:
    """A metric point that breached the rolling baseline."""
    source: str
    service: str
    metric: str
    timestamp: datetime
    value: float
    baseline_mean: float
    baseline_std: float
    zscore: float
    severity: str  # 'warning' | 'critical'


@dataclass
class Incident:
    """A group of anomalies close together in time -- the unit an RCA is built for."""
    id: str
    created_at: datetime
    anomalies: List[Anomaly]
    summary: str = ""
    root_cause: str = ""
    confidence: int = 0
    actions: List[str] = field(default_factory=list)
