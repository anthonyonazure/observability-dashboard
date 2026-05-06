"""Single SQLite store for all agent run records.

Schema:
  AgentRun: per-run row written by any agent that wants to surface in
    the dashboard. Keep schema-flexible via a JSON `metrics` column so
    different agents can report what's relevant without schema churn.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = os.environ.get("AGENTLOG_DATABASE_URL", "sqlite+aiosqlite:///./agentlog.db")
_engine = create_async_engine(DATABASE_URL, echo=False, future=True)
_session = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)             # run_id
    agent: Mapped[str] = mapped_column(String, index=True)                # e.g. "partner-onboarding-agent"
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, index=True)               # ok | partial | failed
    summary: Mapped[str] = mapped_column(String)                          # one-line human summary
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)             # agent-specific metrics
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)


async def init_db() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    async with _session() as s:
        yield s
        await s.commit()
