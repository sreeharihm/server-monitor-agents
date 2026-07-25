import uuid
from datetime import timedelta
from typing import List

from .models import Anomaly, Incident


def correlate(anomalies: List[Anomaly], lag_minutes: int = 5) -> List[Incident]:
    """
    Groups anomalies that occur within `lag_minutes` of each other (chained,
    not just pairwise from the first) into a single Incident, regardless of
    which monitoring source or service they came from. This is what lets a
    Splunk DB-pool anomaly and a Datadog error-rate anomaly end up in the
    same RCA when they're clearly part of the same event.
    """
    if not anomalies:
        return []

    ordered = sorted(anomalies, key=lambda a: a.timestamp)
    groups: List[List[Anomaly]] = []
    current = [ordered[0]]

    for a in ordered[1:]:
        if a.timestamp - current[-1].timestamp <= timedelta(minutes=lag_minutes):
            current.append(a)
        else:
            groups.append(current)
            current = [a]
    groups.append(current)

    return [
        Incident(id=str(uuid.uuid4())[:8], created_at=g[0].timestamp, anomalies=g)
        for g in groups
    ]
