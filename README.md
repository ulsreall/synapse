```
  ____  _   _ _   _  ____  ____  ____
 / ___|| \ | | \ | |/ ___||  _ \/ ___|
 \___ \|  \| |  \| | |  _ | |_) \___ \
  ___) | |\  | |\  | |_| ||  __/ ___) |
 |____/|_| \_|_| \_|\____||_|  |____/
```

# SYNAPSE — Multi-Agent Code Review & Analysis Platform

**SYNAPSE** deploys 10 specialized AI agents in a sequential pipeline to provide
comprehensive code review, security analysis, performance profiling, and automated
documentation. Each agent is purpose-built for a single domain, producing deep,
actionable findings while consuming a predictable token budget.

> Daily throughput: **50–100M+ tokens** across thousands of analyses.

---

## ✨ Key Features

- **10 Specialized Agents** — Security, quality, performance, architecture, testing, docs, dependencies, refactoring, types, and changelogs
- **Deterministic Token Budgets** — Per-agent token estimates let you forecast cost before running
- **Async Pipeline** — Agents execute in sequence; findings from each feed the next
- **Web Dashboard** — Real-time view of pipeline progress and token consumption
- **CLI-First** — `synapse analyze src/` is all you need

---

## 🏗️ Architecture

```
                         ┌─────────────────────────────────┐
                         │          SYNAPSE CLI            │
                         └───────────────┬─────────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │           Pipeline Orchestrator          │
                    └────────────────────┬────────────────────┘
                                         │
     ┌──────────┬──────────┬────────────┼────────────┬──────────┬──────────┐
     ▼          ▼          ▼            ▼            ▼          ▼          ▼
 ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐
 │Security│ │  Code  │ │Perform-│ │Architec-│ │  Test  │ │  Doc   │ │Depend- │
 │Scanner │ │Quality │ │  ance  │ │  ture   │ │Genera- │ │Genera- │ │ ency   │
 │ 18K tk │ │ 15K tk │ │ 16K tk │ │  20K tk │ │ 22K tk │ │ 18K tk │ │ 12K tk │
 └────┬───┘ └────┬───┘ └────┬───┘ └────┬────┘ └────┬───┘ └────┬───┘ └────┬───┘
      │          │          │          │           │          │          │
      ▼          ▼          ▼          ▼           ▼          ▼          ▼
 ┌────────┐ ┌────────┐ ┌────────┐
 │Refactor│ │  Type  │ │Change- │          ┌──────────────────────────────┐
 │Advisor │ │Checker │ │  log   │──────▶   │       Aggregated Report      │
 │ 16K tk │ │ 14K tk │ │ 10K tk │          │  Total: ~161K tokens/file   │
 └────────┘ └────────┘ └────────┘          └──────────────────────────────┘
```

---

## 📊 Token Consumption Breakdown

| # | Agent               | Tokens / Analysis | Capability                          |
|---|---------------------|-------------------|-------------------------------------|
| 1 | Security Scanner    | ~18,000           | OWASP Top 10, injection, XSS, SSRF  |
| 2 | Code Quality        | ~15,000           | Complexity, maintainability, smells  |
| 3 | Performance Analyzer| ~16,000           | Bottlenecks, N+1, memory leaks      |
| 4 | Architecture Review | ~20,000           | SOLID, coupling, cohesion, patterns |
| 5 | Test Generator      | ~22,000           | Unit tests, integration, edge cases |
| 6 | Doc Generator       | ~18,000           | API docs, README, inline comments   |
| 7 | Dependency Audit    | ~12,000           | CVE scan, license, outdated pkgs    |
| 8 | Refactor Advisor    | ~16,000           | DRY violations, extract method      |
| 9 | Type Checker        | ~14,000           | Type inference, null safety         |
|10 | Changelog Generator | ~10,000           | Semver, breaking changes, migration |

**Per-file total: ~161,000 tokens** · **Daily estimate: 50–100M+ tokens**

---

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/nousresearch/synapse.git
cd synapse

# Install in development mode
pip install -e ".[dev]"

# Or install from PyPI
pip install synapse-ai
```

### Requirements

- Python 3.10+
- API key for your preferred LLM provider (OpenAI, Anthropic, or local)

```bash
export SYNAPSE_API_KEY="sk-..."
export SYNAPSE_PROVIDER="openai"  # or "anthropic", "ollama"
```

---

## 📖 Usage

### CLI

```bash
# Analyze a single file
synapse analyze src/app.py

# Analyze an entire directory
synapse analyze src/ --recursive --agents security,performance

# List all available agents
synapse agents

# View token consumption statistics
synapse stats

# Launch the web dashboard
synapse dashboard --port 8080
```

### Python API

```python
import asyncio
from synapse.agents.security_scanner import SecurityScanner
from synapse.agents.code_quality import CodeQuality

async def main():
    config = {"provider": "openai", "model": "gpt-4o"}
    code = open("src/app.py").read()

    scanner = SecurityScanner(config)
    result = await scanner.analyze(code, context={"file": "src/app.py"})

    print(f"Findings: {len(result['findings'])}")
    print(f"Tokens used: {result['tokens_used']}")

asyncio.run(main())
```

### Example: Run the full pipeline

```python
from synapse.pipeline import Pipeline

pipeline = Pipeline(agents="all")
report = pipeline.run("src/app.py")
report.save("analysis_report.md")
```

---

## 🧩 Agents

Each agent is a self-contained async module:

```python
class SecurityScanner:
    """Security analysis agent. Token consumption: ~18K tokens per analysis."""

    def __init__(self, config):
        self.config = config
        self.token_estimate = 18_000

    async def analyze(self, code: str, context: dict) -> dict:
        findings = []
        # ... analysis logic ...
        return {
            "findings": findings,
            "metrics": {"risk_score": 8.5},
            "tokens_used": self.token_estimate,
        }
```

See [`docs/architecture.md`](docs/architecture.md) for the full agent specification.

---

## 📁 Project Structure

```
synapse/
├── README.md
├── cli.py                        # CLI entry point (click)
├── pipeline.py                   # Pipeline orchestrator
├── agents/
│   ├── __init__.py
│   ├── security_scanner.py       # OWASP Top 10, injection, XSS
│   ├── code_quality.py           # Complexity, maintainability
│   ├── performance_analyzer.py   # Bottlenecks, N+1 queries
│   ├── architecture_review.py    # SOLID, design patterns
│   ├── test_generator.py         # Unit & integration tests
│   ├── doc_generator.py          # API docs, README generation
│   ├── dependency_audit.py       # CVE, license compliance
│   ├── refactor_advisor.py       # DRY violations, extract method
│   ├── type_checker.py           # Type inference, null safety
│   └── changelog_generator.py    # Semver, breaking changes
├── examples/
│   └── sample_analysis.py        # Example usage script
├── docs/
│   └── architecture.md           # Detailed architecture docs
└── tests/
    └── ...
```

---

## 🤝 Contributing

```bash
# Fork & clone, then:
pip install -e ".[dev]"
pytest
```

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting PRs.

---

## 📄 License

Apache 2.0 — see [LICENSE](LICENSE) for details.

---

**Built by [Nous Research](https://nousresearch.com)** · Previous submissions: DeepAudit Engine, DocuForge AI, SentinelAI
