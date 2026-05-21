"""
SYNAPSE Configuration - Model settings, agent configs, token budgets,
and pipeline parameters loaded from environment / .env files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, str(default)).lower()
    return val in ("true", "1", "yes")


# Approximate cost per 1K tokens for common models (USD)
MODEL_COST_PER_1K: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
}


@dataclass
class AgentConfig:
    """Configuration for a single analysis agent."""
    name: str = ""
    enabled: bool = True
    estimated_tokens: int = 15_000
    timeout_seconds: int = 120
    max_findings: int = 100
    severity_threshold: str = "info"  # minimum severity to report


@dataclass
class SynapseConfig:
    """Top-level SYNAPSE configuration."""
    # API keys
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    github_token: str = field(default_factory=lambda: _env("GITHUB_TOKEN"))

    # Server
    host: str = field(default_factory=lambda: _env("SYNAPSE_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("SYNAPSE_PORT", 8080))
    debug: bool = field(default_factory=lambda: _env_bool("SYNAPSE_DEBUG", False))

    # Model
    model: str = field(default_factory=lambda: _env("SYNAPSE_MODEL", "gpt-4o"))
    max_tokens: int = field(default_factory=lambda: _env_int("SYNAPSE_MAX_TOKENS", 4096))
    temperature: float = field(default_factory=lambda: float(_env("SYNAPSE_TEMPERATURE", "0.2")))

    # Token limits
    daily_token_limit: int = field(
        default_factory=lambda: _env_int("SYNAPSE_DAILY_TOKEN_LIMIT", 500_000)
    )
    enable_cost_tracking: bool = field(
        default_factory=lambda: _env_bool("SYNAPSE_ENABLE_COST_TRACKING", True)
    )

    # Pipeline
    parallel_agents: bool = field(
        default_factory=lambda: _env_bool("SYNAPSE_PARALLEL_AGENTS", False)
    )
    agent_timeout: int = field(default_factory=lambda: _env_int("SYNAPSE_AGENT_TIMEOUT", 120))

    # Agent definitions (order = pipeline order)
    agents: List[AgentConfig] = field(default_factory=lambda: [
        AgentConfig(name="security_scanner",      estimated_tokens=18_000),
        AgentConfig(name="code_quality",          estimated_tokens=15_000),
        AgentConfig(name="performance_analyzer",  estimated_tokens=16_000),
        AgentConfig(name="architecture_review",   estimated_tokens=20_000),
        AgentConfig(name="test_generator",        estimated_tokens=22_000),
        AgentConfig(name="doc_generator",         estimated_tokens=18_000),
        AgentConfig(name="dependency_audit",      estimated_tokens=12_000),
        AgentConfig(name="refactor_advisor",      estimated_tokens=16_000),
        AgentConfig(name="type_checker",          estimated_tokens=14_000),
        AgentConfig(name="changelog_generator",   estimated_tokens=10_000),
    ])

    @property
    def enabled_agents(self) -> List[AgentConfig]:
        return [a for a in self.agents if a.enabled]

    @property
    def total_estimated_tokens(self) -> int:
        return sum(a.estimated_tokens for a in self.enabled_agents)

    def get_agent_config(self, name: str) -> Optional[AgentConfig]:
        for a in self.agents:
            if a.name == name:
                return a
        return None

    def cost_per_1k(self, direction: str = "input") -> float:
        """Return cost per 1K tokens for the configured model."""
        model_costs = MODEL_COST_PER_1K.get(self.model, MODEL_COST_PER_1K["gpt-4o"])
        return model_costs.get(direction, 0.003)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate USD cost for given token counts."""
        input_cost = (input_tokens / 1000.0) * self.cost_per_1k("input")
        output_cost = (output_tokens / 1000.0) * self.cost_per_1k("output")
        return input_cost + output_cost
