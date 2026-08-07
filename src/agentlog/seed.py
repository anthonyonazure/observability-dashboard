"""Seed the dashboard with synthetic runs across all 8 agents over the
last 30 days, so the demo is a realistic showcase rather than an empty page."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

import structlog

from agentlog.db import AgentRun, init_db, session

log = structlog.get_logger()

NOW = datetime.now(UTC).replace(tzinfo=None)


def _hours_ago(h: float) -> datetime:
    return NOW - timedelta(hours=h)


_AGENTS = [
    "partner-onboarding-agent",
    "ai-account-manager",
    "compliance-evidence-agent",
    "marketing-automation-agent",
    "security-questionnaire-responder",
    "vciso-assistant",
    "renewal-forecasting-agent",
    "pen-test-reporter",
]


def _example_metrics(agent: str) -> dict:
    if agent == "partner-onboarding-agent":
        return {"resources_provisioned": 5, "pdf_pages": 3}
    if agent == "ai-account-manager":
        return {"actions": 5, "delivered_to": ["slack", "teams_channel", "teams_dm"]}
    if agent == "compliance-evidence-agent":
        return {
            "controls_total": 10,
            "controls_passed": 7,
            "controls_failed": 3,
            "framework": "soc2",
        }
    if agent == "marketing-automation-agent":
        return {"drafts_created": 5, "all_passed_review": True}
    if agent == "security-questionnaire-responder":
        return {
            "items_total": 22,
            "auto_answered": 16,
            "needs_review": 6,
            "avg_confidence": 0.69,
        }
    if agent == "vciso-assistant":
        return random.choice(
            [
                {"mode": "qa", "kb_hits": 2, "risk_hits": 1},
                {"mode": "board_update", "open_risks": 9, "closed": 1},
            ]
        )
    if agent == "renewal-forecasting-agent":
        return {"accounts": 12, "total_arr": 1294000, "at_risk": 146791}
    if agent == "pen-test-reporter":
        return {"raw_findings": 19, "unique_groups": 14, "critical": 1, "high": 5}
    return {}


def _summary_for(agent: str, m: dict) -> str:
    if agent == "compliance-evidence-agent":
        return f"{m['controls_passed']}/{m['controls_total']} controls passed ({m['framework'].upper()})"
    if agent == "ai-account-manager":
        return f"briefed AM with {m['actions']} actions"
    if agent == "marketing-automation-agent":
        return f"{m['drafts_created']} personalized drafts in Outlook"
    if agent == "security-questionnaire-responder":
        return f"{m['auto_answered']}/{m['items_total']} auto-answered, {m['needs_review']} need review"
    if agent == "vciso-assistant":
        return (
            "monthly board update generated"
            if m.get("mode") == "board_update"
            else f"answered (KB:{m.get('kb_hits', 0)}, risks:{m.get('risk_hits', 0)})"
        )
    if agent == "renewal-forecasting-agent":
        return f"forecast: ${m['total_arr']:,.0f} ARR, ${m['at_risk']:,.0f} at risk"
    if agent == "pen-test-reporter":
        return f"{m['raw_findings']} findings → {m['unique_groups']} unique ({m['critical']} crit, {m['high']} high)"
    if agent == "partner-onboarding-agent":
        return f"provisioned {m['resources_provisioned']} resources, {m['pdf_pages']}-page PDF"
    return ""


async def seed(n_runs: int = 60) -> None:
    await init_db()
    rng = random.Random(42)

    rows = []
    for i in range(n_runs):
        agent = rng.choice(_AGENTS)
        hours = rng.uniform(0, 30 * 24)
        m = _example_metrics(agent)
        # Status mostly ok, occasionally partial / failed
        status = rng.choices(["ok", "partial", "failed"], weights=[92, 6, 2])[0]
        cost = round(rng.uniform(0.001, 0.12), 4) if rng.random() > 0.15 else 0.0
        tin = rng.randint(500, 8000) if cost else 0
        tout = rng.randint(100, 1500) if cost else 0
        rows.append(
            AgentRun(
                id=uuid.uuid4().hex[:10],
                agent=agent,
                started_at=_hours_ago(hours),
                duration_ms=rng.randint(800, 18_000),
                status=status,
                summary=_summary_for(agent, m),
                metrics=m,
                cost_usd=cost,
                tokens_in=tin,
                tokens_out=tout,
            )
        )

    async with session() as s:
        for r in rows:
            s.add(r)
    log.info("agentlog.seed.complete", n=len(rows))
