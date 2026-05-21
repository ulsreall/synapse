# SYNAPSE Architecture

## Overview

SYNAPSE is a multi-agent code review and analysis platform that deploys 10
specialized AI agents in a sequential pipeline. Each agent focuses on a single
domain of code analysis, producing deep, actionable findings while operating
within a predictable token budget.

```
┌─────────────────────────────────────────────────────────────────┐
│                        SYNAPSE Platform                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐    ┌──────────────────────────┐    ┌───────────┐  │
│  │   CLI   │───▶│   Pipeline Orchestrator   │───▶│  Report   │  │
│  │ (click) │    │  (async sequential exec)  │    │ Generator │  │
│  └─────────┘    └─────────┬────────────────┘    └───────────┘  │
│                           │                                     │
│              ┌────────────┼────────────┐                        │
│              ▼            ▼            ▼                        │
│         ┌────────┐  ┌────────┐  ┌────────┐                     │
│         │ Agent  │  │ Agent  │  │ Agent  │  ... x10            │
│         │ Pool   │  │ Pool   │  │ Pool   │                     │
│         └────────┘  └────────┘  └────────┘                     │
│              │            │            │                        │
│              ▼            ▼            ▼                        │
│         ┌─────────────────────────────────┐                    │
│         │       LLM Provider Layer        │                    │
│         │  (OpenAI / Anthropic / Ollama)  │                    │
│         └─────────────────────────────────┘                    │
│                                                                 │
│         ┌─────────────────────────────────┐                    │
│         │     Token Accounting Layer      │                    │
│         │  (tracking, budgets, alerts)    │                    │
│         └─────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Pipeline

Agents execute sequentially. Each agent receives the raw source code plus a
shared context dict containing file metadata, prior findings, and configuration.
Agents do NOT depend on each other's output — they run independently against
the same input.

### Pipeline Execution Order

```
Input Code
    │
    ▼
┌──────────────────────┐
│ 1. Security Scanner   │  18K tokens   OWASP Top 10, injection, XSS, SSRF
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 2. Code Quality       │  15K tokens   Complexity, maintainability, smells
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 3. Performance Analy. │  16K tokens   Bottlenecks, N+1, memory leaks
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 4. Architecture Rev.  │  20K tokens   SOLID, coupling, cohesion, patterns
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 5. Test Generator     │  22K tokens   Unit tests, integration, edge cases
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 6. Doc Generator      │  18K tokens   API docs, README, inline comments
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 7. Dependency Audit   │  12K tokens   CVE scan, license, outdated pkgs
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 8. Refactor Advisor   │  16K tokens   DRY violations, extract method
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 9. Type Checker       │  14K tokens   Type inference, null safety
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 10. Changelog Gen.    │  10K tokens   Semver, breaking changes
└──────────┬───────────┘
           ▼
     Aggregated Report
     (~161K tokens/file)
```

---

## Token Consumption Model

### Per-Agent Budgets

Each agent has a fixed token estimate per analysis. This estimate covers:

| Component            | Token Share | Description                                    |
|----------------------|-------------|------------------------------------------------|
| **System Prompt**    | ~2,000      | Agent persona, role, output format instructions|
| **Code Injection**   | ~4,000–8,000| Source code being analyzed (varies by file size)|
| **Few-shot Examples**| ~2,000      | Example findings and expected output format    |
| **Analysis Chain**   | ~4,000–8,000| Multi-step reasoning and finding generation    |
| **Output Generation**| ~2,000      | Structured JSON findings and metrics           |

### Daily Consumption Estimates

| Scale          | Files/Day | Tokens/Day      | Estimated Cost (GPT-4o) |
|----------------|-----------|-----------------|------------------------|
| Small team     | 100       | ~16M tokens     | ~$24                   |
| Medium org     | 1,000     | ~161M tokens    | ~$240                  |
| Large platform | 10,000    | ~1.6B tokens    | ~$2,400                |

### Optimization Strategies

1. **Selective Agent Execution** — Run only relevant agents per file
2. **Incremental Analysis** — Only analyze changed files (git diff)
3. **Tiered Analysis** — Quick scan (2-3 agents) vs. deep scan (all 10)
4. **Caching** — Cache results for unchanged files
5. **Model Selection** — Use smaller models for simpler agents

---

## Agent Interface Contract

Every agent implements the same interface:

```python
class BaseAgent:
    """Base agent interface. All agents must implement this contract."""

    def __init__(self, config: dict):
        self.config = config
        self.token_estimate: int = 0  # Tokens per analysis

    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze source code and return findings.

        Args:
            code: The source code to analyze.
            context: Additional context including:
                - file: File path being analyzed
                - version: Project version (optional)
                - prior_findings: Findings from previous agents (optional)
                - config: Additional agent-specific config

        Returns:
            dict with keys:
                - findings: List[dict] — Individual findings
                - metrics: dict — Aggregate metrics and scores
                - tokens_used: int — Actual tokens consumed
        """
        raise NotImplementedError
```

### Finding Schema

```json
{
    "type": "finding_category",
    "severity": "error | warning | info",
    "line": 42,
    "message": "Human-readable description of the issue.",
    "suggestion": "Actionable suggestion to fix the issue.",
    "metadata": {}
}
```

---

## Scaling Strategy

### Horizontal Scaling

```
                    ┌──────────────────┐
                    │  Load Balancer   │
                    └────────┬─────────┘
               ┌─────────────┼─────────────┐
               ▼             ▼             ▼
        ┌────────────┐ ┌────────────┐ ┌────────────┐
        │ Worker Pod │ │ Worker Pod │ │ Worker Pod │
        │ (10 agents)│ │ (10 agents)│ │ (10 agents)│
        └────────────┘ └────────────┘ └────────────┘
```

- Each worker runs a full 10-agent pipeline
- Files are distributed across workers via a message queue
- Token accounting is centralized in a shared database

### Vertical Scaling

- Agents are CPU-light (mostly LLM API calls)
- Memory usage is proportional to concurrent file analysis
- Bottleneck is API rate limits, not compute

### Cost Control

1. **Token Budget Alerts** — Warn when approaching daily limits
2. **Priority Queues** — Critical files analyzed first
3. **Graceful Degradation** — Skip lower-priority agents when budget is tight
4. **Usage Dashboard** — Real-time visibility into token consumption

---

## Technology Stack

- **Runtime**: Python 3.10+
- **CLI**: Click
- **Async**: asyncio
- **AST Parsing**: Python ast module (built-in)
- **LLM Providers**: OpenAI, Anthropic, Ollama (pluggable)
- **Dashboard**: FastAPI + WebSockets (planned)
- **Storage**: SQLite (local), PostgreSQL (production)
