"""
SYNAPSE Token Tracker - Monitors token consumption per agent, per hour,
and per day. Provides cost estimation and budget enforcement.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import TokenUsage


@dataclass
class HourlyAggregate:
    hour_ts: float  # start of the hour (floored)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    request_count: int = 0


@dataclass
class DailyAggregate:
    date_str: str  # YYYY-MM-DD
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    request_count: int = 0
    per_agent: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


class TokenTracker:
    """
    Tracks token consumption across the SYNAPSE agent pipeline.

    Provides:
    - Per-agent token accounting
    - Hourly and daily aggregations
    - Cost estimation using model pricing tables
    - Budget limit enforcement
    """

    def __init__(self, daily_limit: int = 500_000, cost_per_1k_input: float = 0.0025,
                 cost_per_1k_output: float = 0.01):
        self.daily_limit = daily_limit
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output

        # Full history
        self._history: List[TokenUsage] = []

        # Per-agent aggregates
        self._agent_totals: Dict[str, int] = defaultdict(int)
        self._agent_costs: Dict[str, float] = defaultdict(float)
        self._agent_counts: Dict[str, int] = defaultdict(int)

        # Hourly buckets (key = floored unix timestamp)
        self._hourly: Dict[int, HourlyAggregate] = {}

        # Daily buckets (key = "YYYY-MM-DD")
        self._daily: Dict[str, DailyAggregate] = {}

    # ── Public API ─────────────────────────────────────────────

    def record(self, usage: TokenUsage) -> TokenUsage:
        """Record a token usage event, update all aggregates."""
        # Estimate cost if not set
        if usage.estimated_cost_usd == 0.0:
            usage.estimated_cost_usd = self.estimate_cost(
                usage.prompt_tokens, usage.completion_tokens
            )

        self._history.append(usage)

        # Per-agent
        self._agent_totals[usage.agent_name] += usage.total_tokens
        self._agent_costs[usage.agent_name] += usage.estimated_cost_usd
        self._agent_counts[usage.agent_name] += 1

        # Hourly
        hour_ts = self._floor_to_hour(usage.timestamp)
        if hour_ts not in self._hourly:
            self._hourly[hour_ts] = HourlyAggregate(hour_ts=hour_ts)
        agg = self._hourly[hour_ts]
        agg.total_tokens += usage.total_tokens
        agg.total_cost_usd += usage.estimated_cost_usd
        agg.request_count += 1

        # Daily
        date_str = self._ts_to_date(usage.timestamp)
        if date_str not in self._daily:
            self._daily[date_str] = DailyAggregate(date_str=date_str)
        dag = self._daily[date_str]
        dag.total_tokens += usage.total_tokens
        dag.total_cost_usd += usage.estimated_cost_usd
        dag.request_count += 1
        dag.per_agent[usage.agent_name] += usage.total_tokens

        return usage

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate USD cost for the given token counts."""
        in_cost = (prompt_tokens / 1000.0) * self.cost_per_1k_input
        out_cost = (completion_tokens / 1000.0) * self.cost_per_1k_output
        return in_cost + out_cost

    def today_usage(self) -> int:
        """Total tokens used today."""
        date_str = self._ts_to_date(time.time())
        dag = self._daily.get(date_str)
        return dag.total_tokens if dag else 0

    def today_cost(self) -> float:
        """Total estimated cost today in USD."""
        date_str = self._ts_to_date(time.time())
        dag = self._daily.get(date_str)
        return dag.total_cost_usd if dag else 0.0

    def budget_remaining(self) -> int:
        """How many tokens remain before hitting the daily limit."""
        return max(0, self.daily_limit - self.today_usage())

    def is_over_budget(self) -> bool:
        return self.today_usage() >= self.daily_limit

    def agent_summary(self) -> Dict[str, Dict]:
        """Return per-agent totals: {agent: {tokens, cost, count}}."""
        summary = {}
        for agent in sorted(self._agent_totals.keys()):
            summary[agent] = {
                "total_tokens": self._agent_totals[agent],
                "estimated_cost_usd": round(self._agent_costs[agent], 6),
                "request_count": self._agent_counts[agent],
                "avg_tokens": (
                    self._agent_totals[agent] // self._agent_counts[agent]
                    if self._agent_counts[agent] else 0
                ),
            }
        return summary

    def hourly_breakdown(self, hours: int = 24) -> List[Dict]:
        """Return last N hours of usage."""
        now = time.time()
        cutoff = now - hours * 3600
        result = []
        for ts in sorted(self._hourly.keys()):
            if ts >= cutoff:
                agg = self._hourly[ts]
                result.append({
                    "hour": self._ts_to_iso(ts),
                    "tokens": agg.total_tokens,
                    "cost_usd": round(agg.total_cost_usd, 6),
                    "requests": agg.request_count,
                })
        return result

    def daily_breakdown(self, days: int = 7) -> List[Dict]:
        """Return last N days of usage."""
        result = []
        for date_str in sorted(self._daily.keys())[-days:]:
            dag = self._daily[date_str]
            result.append({
                "date": date_str,
                "tokens": dag.total_tokens,
                "cost_usd": round(dag.total_cost_usd, 6),
                "requests": dag.request_count,
                "per_agent": dict(dag.per_agent),
            })
        return result

    def total_stats(self) -> Dict:
        """Lifetime totals."""
        total_tokens = sum(u.total_tokens for u in self._history)
        total_cost = sum(u.estimated_cost_usd for u in self._history)
        return {
            "total_requests": len(self._history),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "daily_limit": self.daily_limit,
            "today_tokens": self.today_usage(),
            "today_cost_usd": round(self.today_cost(), 6),
            "budget_remaining": self.budget_remaining(),
        }

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _floor_to_hour(ts: float) -> float:
        return float(int(ts) // 3600 * 3600)

    @staticmethod
    def _ts_to_date(ts: float) -> str:
        import datetime
        return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")

    @staticmethod
    def _ts_to_iso(ts: float) -> str:
        import datetime
        return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:00:00Z")
