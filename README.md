# Multi-source monitoring agent

Polls Splunk, AWS CloudWatch, Prometheus, and Datadog on a schedule, detects
anomalies against a rolling per-metric baseline, correlates anomalies that
land close together in time (even across different tools), and writes a
root-cause-analysis report for each incident.

## How it works

```
connectors (splunk / cloudwatch / prometheus / datadog)
        │  fetch() → MetricPoint[]
        ▼
   AnomalyDetector          rolling mean/std per (source, service, metric)
        │  evaluate() → Anomaly[]
        ▼
     correlate()            groups anomalies within `lag_minutes` of each other
        │  → Incident[]
        ▼
     build_rca()            rule-based summary + root cause + actions
        │  (optional: rewritten by Claude if ANTHROPIC_API_KEY is set)
        ▼
  output/incidents/*.json
```

Each connector only runs if it's configured (credentials present) — missing
ones are skipped, not treated as errors, so you can start with just one tool
and add the rest later.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in credentials for the tools you're using
```

Edit `config.yaml` to define what each connector should watch — one entry
per (service, metric) pair, with whatever query syntax that tool needs
(SPL for Splunk, PromQL for Prometheus, a CloudWatch namespace/metric, or a
Datadog metric query). The example file has one working example per source.

## Run

```bash
python main.py
```

This runs one poll immediately, then keeps polling on the interval set by
`poll_interval_minutes` in `config.yaml`. Incident reports land in
`output/incidents/<id>.json`. Press Ctrl+C to stop.

## Tuning detection

In `agent/detector.py`, `AnomalyDetector(...)` takes:
- `window_size` — how many recent points make up the baseline (default 20)
- `min_samples` — how many points before it starts flagging anomalies (default 8)
- `warning_z` / `critical_z` — z-score thresholds (default 2.5 / 3.5)

In `config.yaml`, `lag_minutes` controls how close in time two anomalies
need to be to count as the same incident.

## Optional: LLM-refined RCA

By default the root-cause write-up is rule-based (deterministic, no external
calls). Set `ANTHROPIC_API_KEY` in `.env` and `pip install anthropic` to have
Claude rewrite the root-cause section in clearer language once anomalies are
already detected and correlated — the detection and correlation logic itself
never depends on an LLM call.

## Known limitations / next steps for production use

- **Baseline state is in-memory** and resets on restart. For anything
  long-running, persist `AnomalyDetector.history` to SQLite or Redis.
- **No de-duplication** — if a metric stays anomalous across multiple polls,
  you'll get a new incident each time the gap between flagged points exceeds
  `lag_minutes`. Add an "open incident" tracker keyed by (service, metric) if
  you want ongoing incidents updated instead of re-created.
- **No alerting integration yet** — incidents currently only write to
  `output/incidents/`. Add a Slack webhook, PagerDuty call, or a POST to a
  dashboard endpoint at the end of `poll()` in `main.py`.
- **Correlation is temporal only**, not topology-aware. If you have a
  service dependency graph, use it to weight which anomaly is more likely
  upstream instead of "whichever happened first."

## Additional docs

- See `INSTRUCTIONS.md` for setup, run, and troubleshooting instructions.
- See `WORKING_DOC.md` for architecture notes, operations workflow, and backlog ideas.
