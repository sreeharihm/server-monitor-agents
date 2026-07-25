import os

from .models import Incident


def _rule_based_rca(incident: Incident) -> Incident:
    """Deterministic RCA draft -- always runs, needs no external API."""
    anomalies = sorted(incident.anomalies, key=lambda a: a.timestamp)
    primary = anomalies[0]
    services = sorted({f"{a.source}:{a.service}" for a in anomalies})
    max_severity = "critical" if any(a.severity == "critical" for a in anomalies) else "warning"

    incident.summary = (
        f"{len(anomalies)} anomal{'y' if len(anomalies) == 1 else 'ies'} detected across "
        f"{len(services)} service(s): {', '.join(services)}."
    )

    if len(anomalies) > 1:
        lag_minutes = (anomalies[-1].timestamp - anomalies[0].timestamp).total_seconds() / 60
        others = ", ".join(s for s in services if s != f"{primary.source}:{primary.service}")
        incident.root_cause = (
            f"Anomaly on {primary.source}:{primary.service} ({primary.metric}) occurred first, "
            f"followed within {lag_minutes:.1f} min by anomalies on {others}. "
            f"This temporal ordering suggests {primary.service} is the likely upstream trigger, "
            f"but this is a correlation, not a confirmed causal link -- verify against logs and traces "
            f"before acting on it."
        )
        incident.confidence = min(95, 55 + (20 if lag_minutes < 5 else 0) + (10 if len(anomalies) > 2 else 0))
    else:
        incident.root_cause = (
            f"Isolated anomaly on {primary.source}:{primary.service} ({primary.metric}): "
            f"value {primary.value:.2f} vs baseline {primary.baseline_mean:.2f} "
            f"(z-score {primary.zscore:.1f}). No correlated signal found in other monitored services "
            f"within the configured lag window."
        )
        incident.confidence = 50

    incident.actions = [
        f"Inspect {primary.source}:{primary.service} dashboards/logs around {primary.timestamp.isoformat()}",
        "Check recent deploys or config changes to the affected service(s)",
        "Confirm whether the anomaly has self-resolved or is still active",
    ]
    if max_severity == "critical":
        incident.actions.insert(0, "Page on-call -- this incident is above the critical threshold")

    return incident


def _llm_rca(incident: Incident) -> Incident:
    """
    Optional: rewrite the root-cause narrative with an LLM for a clearer,
    more specific write-up. Runs only if the `anthropic` package is installed
    and ANTHROPIC_API_KEY is set -- otherwise the rule-based draft above stands.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return incident
    try:
        import anthropic
    except ImportError:
        return incident

    anomaly_desc = "\n".join(
        f"- {a.source}:{a.service} metric={a.metric} value={a.value:.2f} "
        f"baseline={a.baseline_mean:.2f} z={a.zscore:.1f} severity={a.severity} at {a.timestamp.isoformat()}"
        for a in sorted(incident.anomalies, key=lambda a: a.timestamp)
    )
    prompt = (
        "You are an SRE assistant. Given these correlated monitoring anomalies, write a short "
        "root cause analysis with three parts: SUMMARY, PROBABLE ROOT CAUSE (explicitly framed as a "
        "hypothesis, not a confirmed fact), and 3-5 RECOMMENDED ACTIONS. Be concise and concrete, "
        "and do not overstate confidence beyond what the data supports.\n\n"
        f"Anomalies:\n{anomaly_desc}"
    )

    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        if text.strip():
            incident.root_cause = text.strip()
    except Exception as e:
        print(f"[rca] LLM refinement failed, keeping rule-based RCA: {e}")

    return incident


def build_rca(incident: Incident) -> Incident:
    incident = _rule_based_rca(incident)
    incident = _llm_rca(incident)
    return incident
