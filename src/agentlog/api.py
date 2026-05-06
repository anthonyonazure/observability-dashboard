"""FastAPI app: dashboard UI + a `POST /v1/runs` ingest endpoint that
agents can call to record themselves.

Aggregations are computed on the fly from SQLite; no separate
materialized views (the run table stays small enough for hundreds of
agents-per-day for years before that matters)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from agentlog.db import AgentRun, init_db, session

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"

app = FastAPI(title="Agent Observability Dashboard", version="0.1.0")
templates = Jinja2Templates(directory=str(TEMPLATES))


@app.on_event("startup")
async def _startup() -> None:
    await init_db()


# ---------- Aggregations ----------

async def _aggregate(window_hours: int = 24 * 7) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=window_hours)
    async with session() as s:
        rows = (await s.execute(select(AgentRun).where(AgentRun.started_at >= cutoff))).scalars().all()
    runs = list(rows)
    by_agent: dict[str, list[AgentRun]] = defaultdict(list)
    for r in runs:
        by_agent[r.agent].append(r)

    per_agent = []
    for agent, agent_runs in sorted(by_agent.items()):
        statuses = Counter(r.status for r in agent_runs)
        cost = sum(r.cost_usd for r in agent_runs)
        durations = sorted(r.duration_ms for r in agent_runs)
        p50 = durations[len(durations)//2] if durations else 0
        p95 = durations[max(0, int(len(durations)*0.95) - 1)] if durations else 0
        per_agent.append({
            "agent": agent,
            "runs": len(agent_runs),
            "ok": statuses.get("ok", 0),
            "partial": statuses.get("partial", 0),
            "failed": statuses.get("failed", 0),
            "ok_rate_pct": round(statuses.get("ok", 0) / max(len(agent_runs), 1) * 100, 1),
            "cost_usd": round(cost, 4),
            "p50_ms": p50,
            "p95_ms": p95,
            "tokens_in": sum(r.tokens_in for r in agent_runs),
            "tokens_out": sum(r.tokens_out for r in agent_runs),
        })

    return {
        "window_hours": window_hours,
        "total_runs": len(runs),
        "total_cost_usd": round(sum(r.cost_usd for r in runs), 4),
        "by_agent": per_agent,
        "ok_rate_overall": round(
            sum(1 for r in runs if r.status == "ok") / max(len(runs), 1) * 100, 1
        ),
    }


async def _recent(limit: int = 30) -> list[AgentRun]:
    async with session() as s:
        rows = (await s.execute(select(AgentRun).order_by(desc(AgentRun.started_at)).limit(limit))).scalars().all()
    return list(rows)


# ---------- HTML routes ----------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, window: int = 24 * 7):
    agg = await _aggregate(window)
    recent = await _recent(40)
    return templates.TemplateResponse(
        request, "dashboard.html",
        {"agg": agg, "recent": recent, "window": window},
    )


@app.get("/agent/{agent}", response_class=HTMLResponse)
async def agent_detail(request: Request, agent: str):
    async with session() as s:
        rows = (await s.execute(
            select(AgentRun).where(AgentRun.agent == agent).order_by(desc(AgentRun.started_at)).limit(100)
        )).scalars().all()
    return templates.TemplateResponse(
        request, "agent_detail.html",
        {"agent": agent, "runs": list(rows)},
    )


# ---------- JSON ingest endpoint (for agents to call) ----------

class RunIn(BaseModel):
    id: str
    agent: str
    started_at: datetime
    duration_ms: int = 0
    status: str = "ok"
    summary: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0


@app.post("/v1/runs")
async def post_run(body: RunIn) -> JSONResponse:
    async with session() as s:
        s.add(AgentRun(
            id=body.id, agent=body.agent,
            started_at=body.started_at.replace(tzinfo=None) if body.started_at.tzinfo else body.started_at,
            duration_ms=body.duration_ms, status=body.status, summary=body.summary,
            metrics=body.metrics, cost_usd=body.cost_usd,
            tokens_in=body.tokens_in, tokens_out=body.tokens_out,
        ))
    return JSONResponse({"ok": True, "id": body.id})


@app.get("/health")
async def health():
    return {"status": "ok"}
