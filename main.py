import json
import logging
import os

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from agent.connectors.cloudwatch_connector import CloudWatchConnector
from agent.connectors.datadog_connector import DatadogConnector
from agent.connectors.prometheus_connector import PrometheusConnector
from agent.connectors.splunk_connector import SplunkConnector
from agent.correlator import correlate
from agent.detector import AnomalyDetector
from agent.rca import build_rca
from agents.master_agent.a2a_connector import A2AConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agent")

load_dotenv()

with open("config.yaml") as f:
    CFG = yaml.safe_load(f)

_a2a_cfg = CFG.get("a2a_agents", {})

CONNECTORS = [
    SplunkConnector(CFG.get("splunk", {}).get("watches", [])),
    CloudWatchConnector(CFG.get("cloudwatch", {}).get("watches", [])),
    PrometheusConnector(CFG.get("prometheus", {}).get("watches", [])),
    DatadogConnector(CFG.get("datadog", {}).get("watches", [])),
    # A2A mock agents — active when their sub-agent servers are running
    A2AConnector(_a2a_cfg.get("cloudwatch", {}).get("url", "http://localhost:8001"), "cloudwatch-a2a"),
    A2AConnector(_a2a_cfg.get("prometheus", {}).get("url", "http://localhost:8002"), "prometheus-a2a"),
]

detector = AnomalyDetector()

OUTPUT_DIR = "output/incidents"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def poll():
    log.info("polling monitoring sources...")
    all_points = []

    for connector in CONNECTORS:
        if not connector.is_configured():
            log.info(f"[{connector.name}] not configured, skipping")
            continue
        points = connector.fetch(CFG.get("lookback_minutes", 15))
        log.info(f"[{connector.name}] fetched {len(points)} point(s)")
        all_points.extend(points)

    anomalies = detector.evaluate(all_points)
    if not anomalies:
        log.info("no anomalies this cycle")
        return

    incidents = correlate(anomalies, lag_minutes=CFG.get("lag_minutes", 5))

    for incident in incidents:
        incident = build_rca(incident)
        report = {
            "id": incident.id,
            "created_at": incident.created_at.isoformat(),
            "summary": incident.summary,
            "root_cause": incident.root_cause,
            "confidence": incident.confidence,
            "actions": incident.actions,
            "anomalies": [
                {
                    "source": a.source,
                    "service": a.service,
                    "metric": a.metric,
                    "value": a.value,
                    "baseline_mean": a.baseline_mean,
                    "zscore": a.zscore,
                    "severity": a.severity,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in incident.anomalies
            ],
        }
        path = os.path.join(OUTPUT_DIR, f"{incident.id}.json")
        with open(path, "w") as out:
            json.dump(report, out, indent=2, default=str)

        log.warning(f"INCIDENT {incident.id}: {incident.summary} (confidence {incident.confidence}%) -> {path}")


if __name__ == "__main__":
    poll()  # run once immediately so you see output right away

    interval = CFG.get("poll_interval_minutes", 5)
    scheduler = BlockingScheduler()
    scheduler.add_job(poll, "interval", minutes=interval)
    log.info(f"scheduler started, polling every {interval} min. Ctrl+C to stop.")
    scheduler.start()
