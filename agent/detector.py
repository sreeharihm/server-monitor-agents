import statistics
from collections import defaultdict, deque
from typing import List

from .models import Anomaly, MetricPoint


class AnomalyDetector:
    """
    Maintains a rolling baseline (mean/std) per (source, service, metric) stream
    and flags points that fall too many standard deviations above it.

    NOTE: state lives in memory and resets if the process restarts. For a
    longer-running deployment, swap `self.history` for something backed by
    SQLite/Redis so the baseline survives restarts.
    """

    def __init__(
        self,
        window_size: int = 20,
        warning_z: float = 2.5,
        critical_z: float = 3.5,
        min_samples: int = 8,
    ):
        self.window_size = window_size
        self.warning_z = warning_z
        self.critical_z = critical_z
        self.min_samples = min_samples
        self.history = defaultdict(lambda: deque(maxlen=window_size))

    @staticmethod
    def _key(p: MetricPoint):
        return (p.source, p.service, p.metric)

    def evaluate(self, points: List[MetricPoint]) -> List[Anomaly]:
        anomalies: List[Anomaly] = []
        for p in points:
            key = self._key(p)
            hist = self.history[key]

            if len(hist) >= self.min_samples:
                mean = statistics.mean(hist)
                std = statistics.pstdev(hist) or 1e-6
                z = (p.value - mean) / std

                if z >= self.critical_z:
                    anomalies.append(
                        Anomaly(p.source, p.service, p.metric, p.timestamp, p.value, mean, std, z, "critical")
                    )
                elif z >= self.warning_z:
                    anomalies.append(
                        Anomaly(p.source, p.service, p.metric, p.timestamp, p.value, mean, std, z, "warning")
                    )

            hist.append(p.value)
        return anomalies
