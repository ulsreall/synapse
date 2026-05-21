#!/usr/bin/env python3
"""SYNAPSE - Multi-Agent Code Review Platform Web Dashboard"""

import uuid
import random
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__)
app.secret_key = 'synapse-secret-key-2026'

# ──────────────────────────────────────────────────────────────
# In-memory data store
# ──────────────────────────────────────────────────────────────

AGENTS = [
    {"id": "sec-01", "name": "Security Sentinel", "icon": "🛡️", "description": "Scans for security vulnerabilities, injection attacks, and auth flaws", "category": "security", "status": "active", "tokens_used": 0, "success_rate": 0, "total_runs": 0, "last_run": None, "avg_time_ms": 0},
    {"id": "perf-02", "name": "Performance Oracle", "icon": "⚡", "description": "Identifies bottlenecks, N+1 queries, and optimization opportunities", "category": "performance", "status": "active", "tokens_used": 0, "success_rate": 0, "total_runs": 0, "last_run": None, "avg_time_ms": 0},
    {"id": "style-03", "name": "Style Architect", "icon": "🎨", "description": "Enforces code style, naming conventions, and formatting standards", "category": "style", "status": "idle", "tokens_used": 0, "success_rate": 0, "total_runs": 0, "last_run": None, "avg_time_ms": 0},
    {"id": "test-04", "name": "Test Weaver", "icon": "🧪", "description": "Analyzes test coverage and suggests missing test cases", "category": "testing", "status": "active", "tokens_used": 0, "success_rate": 0, "total_runs": 0, "last_run": None, "avg_time_ms": 0},
    {"id": "doc-05", "name": "Doc Sage", "icon": "📚", "description": "Reviews documentation quality and suggests improvements", "category": "documentation", "status": "idle", "tokens_used": 0, "success_rate": 0, "total_runs": 0, "last_run": None, "avg_time_ms": 0},
    {"id": "arch-06", "name": "Architecture Guardian", "icon": "🏗️", "description": "Evaluates architectural patterns and design decisions", "category": "architecture", "status": "active", "tokens_used": 0, "success_rate": 0, "total_runs": 0, "last_run": None, "avg_time_ms": 0},
    {"id": "dep-07", "name": "Dependency Watchdog", "icon": "🔍", "description": "Checks for outdated deps, license issues, and supply chain risks", "category": "dependencies", "status": "idle", "tokens_used": 0, "success_rate": 0, "total_runs": 0, "last_run": None, "avg_time_ms": 0},
    {"id": "err-08", "name": "Error Philosopher", "icon": "🧠", "description": "Reviews error handling, edge cases, and failure modes", "category": "reliability", "status": "active", "tokens_used": 0, "success_rate": 0, "total_runs": 0, "last_run": None, "avg_time_ms": 0},
    {"id": "type-09", "name": "Type Inquisitor", "icon": "🔬", "description": "Analyzes type safety, type coverage, and type correctness", "category": "types", "status": "idle", "tokens_used": 0, "success_rate": 0, "total_runs": 0, "last_run": None, "avg_time_ms": 0},
    {"id": "conc-10", "name": "Concurrency Sage", "icon": "🔄", "description": "Detects race conditions, deadlocks, and concurrency issues", "category": "concurrency", "status": "active", "tokens_used": 0, "success_rate": 0, "total_runs": 0, "last_run": None, "avg_time_ms": 0},
]

analyses = {}  # id -> analysis data
daily_stats = []  # list of daily stat records
hourly_stats = []  # list of hourly stat records


def _generate_sample_data():
    """Populate agents and analyses with realistic sample data."""
    now = datetime.utcnow()

    # Assign realistic stats to each agent
    stats_map = {
        "sec-01": {"tokens": 1_247_830, "rate": 94.2, "runs": 1847, "avg_ms": 2340},
        "perf-02": {"tokens": 982_150, "rate": 91.7, "runs": 1523, "avg_ms": 1890},
        "style-03": {"tokens": 2_103_440, "rate": 97.8, "runs": 3201, "avg_ms": 980},
        "test-04": {"tokens": 756_220, "rate": 88.3, "runs": 1102, "avg_ms": 3120},
        "doc-05": {"tokens": 445_670, "rate": 96.1, "runs": 876, "avg_ms": 1450},
        "arch-06": {"tokens": 678_990, "rate": 89.5, "runs": 934, "avg_ms": 2780},
        "dep-07": {"tokens": 334_120, "rate": 92.4, "runs": 1456, "avg_ms": 1120},
        "err-08": {"tokens": 567_880, "rate": 90.1, "runs": 1289, "avg_ms": 2010},
        "type-09": {"tokens": 891_340, "rate": 93.6, "runs": 1678, "avg_ms": 1670},
        "conc-10": {"tokens": 423_560, "rate": 87.9, "runs": 743, "avg_ms": 2890},
    }

    for agent in AGENTS:
        s = stats_map[agent["id"]]
        agent["tokens_used"] = s["tokens"]
        agent["success_rate"] = s["rate"]
        agent["total_runs"] = s["runs"]
        agent["avg_time_ms"] = s["avg_ms"]
        agent["last_run"] = (now - timedelta(minutes=random.randint(1, 120))).isoformat() + "Z"

    # Generate sample analyses
    sample_analyses = [
        {
            "code": '''def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    result = db.execute(query)
    if result:
        session['user'] = username
        return redirect('/dashboard')
    return render_template('login.html', error='Invalid credentials')''',
            "language": "python",
            "filename": "auth.py",
            "agents": ["sec-01", "perf-02", "err-08"],
            "score": 32,
            "created": (now - timedelta(hours=2)).isoformat() + "Z",
            "findings": [
                {"agent": "Security Sentinel", "severity": "critical", "message": "SQL injection vulnerability: user input directly interpolated into query string", "line": 2},
                {"agent": "Security Sentinel", "severity": "critical", "message": "Plaintext password comparison - passwords should be hashed with bcrypt/argon2", "line": 2},
                {"agent": "Security Sentinel", "severity": "high", "message": "No CSRF protection on login form submission", "line": 1},
                {"agent": "Performance Oracle", "severity": "medium", "message": "No index hint for username+password composite lookup", "line": 2},
                {"agent": "Error Philosopher", "severity": "high", "message": "No exception handling for database connection failures", "line": 3},
                {"agent": "Error Philosopher", "severity": "medium", "message": "No rate limiting on login attempts - brute force vulnerability", "line": 1},
            ],
            "tokens_used": 4520,
            "duration_ms": 3420,
        },
        {
            "code": '''class DataProcessor:
    def __init__(self):
        self.cache = {}
        self.results = []

    def process_batch(self, items):
        for item in items:
            if item.id in self.cache:
                self.results.append(self.cache[item.id])
            else:
                result = self._expensive_compute(item)
                self.cache[item.id] = result
                self.results.append(result)
        return self.results

    def _expensive_compute(self, item):
        import time
        time.sleep(0.1)  # simulate work
        return {"computed": True, "value": item.data * 2}''',
            "language": "python",
            "filename": "processor.py",
            "agents": ["perf-02", "arch-06", "conc-10"],
            "score": 71,
            "created": (now - timedelta(hours=5)).isoformat() + "Z",
            "findings": [
                {"agent": "Performance Oracle", "severity": "high", "message": "Cache grows unbounded - implement LRU eviction or TTL", "line": 3},
                {"agent": "Performance Oracle", "severity": "medium", "message": "time.sleep in compute blocks the event loop", "line": 18},
                {"agent": "Architecture Guardian", "severity": "medium", "message": "Mutable shared state (results) accumulates across calls", "line": 5},
                {"agent": "Concurrency Sage", "severity": "high", "message": "Cache dict is not thread-safe for concurrent access", "line": 3},
                {"agent": "Concurrency Sage", "severity": "info", "message": "Consider using functools.lru_cache for memoization pattern", "line": 14},
            ],
            "tokens_used": 3890,
            "duration_ms": 2870,
        },
        {
            "code": '''import React, { useState, useEffect } from 'react';

export function UserList() {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch('/api/users')
            .then(res => res.json())
            .then(data => {
                setUsers(data);
                setLoading(false);
            });
    }, []);

    if (loading) return <div>Loading...</div>;

    return (
        <ul>
            {users.map(user => (
                <li key={user.id}>
                    {user.name} - {user.email}
                </li>
            ))}
        </ul>
    );
}''',
            "language": "javascript",
            "filename": "UserList.jsx",
            "agents": ["err-08", "sec-01", "test-04"],
            "score": 68,
            "created": (now - timedelta(hours=8)).isoformat() + "Z",
            "findings": [
                {"agent": "Error Philosopher", "severity": "high", "message": "No error handling for failed fetch requests", "line": 8},
                {"agent": "Error Philosopher", "severity": "medium", "message": "Loading state never reset on error - component stuck in loading", "line": 6},
                {"agent": "Security Sentinel", "severity": "medium", "message": "User email rendered without XSS sanitization", "line": 19},
                {"agent": "Test Weaver", "severity": "medium", "message": "No test coverage for error states or empty data", "line": 1},
                {"agent": "Test Weaver", "severity": "info", "message": "Consider adding loading skeleton instead of plain text", "line": 14},
            ],
            "tokens_used": 3120,
            "duration_ms": 2340,
        },
        {
            "code": '''fn fibonacci(n: u64) -> u64 {
    if n <= 1 {
        return n;
    }
    fibonacci(n - 1) + fibonacci(n - 2)
}

fn main() {
    let result = fibonacci(45);
    println!("fib(45) = {}", result);
}''',
            "language": "rust",
            "filename": "fib.rs",
            "agents": ["perf-02", "style-03", "doc-05"],
            "score": 55,
            "created": (now - timedelta(hours=12)).isoformat() + "Z",
            "findings": [
                {"agent": "Performance Oracle", "severity": "critical", "message": "Exponential time complexity O(2^n) - use iterative or memoized approach", "line": 1},
                {"agent": "Performance Oracle", "severity": "high", "message": "Stack overflow risk for large n values with recursion", "line": 5},
                {"agent": "Style Architect", "severity": "info", "message": "Consider using u128 for larger fibonacci values", "line": 1},
                {"agent": "Doc Sage", "severity": "medium", "message": "Missing function documentation and parameter descriptions", "line": 1},
                {"agent": "Doc Sage", "severity": "info", "message": "No panic/error documentation for edge cases", "line": 1},
            ],
            "tokens_used": 2670,
            "duration_ms": 1890,
        },
        {
            "code": '''export class OrderService {
    constructor(private db: Database, private logger: Logger) {}

    async createOrder(userId: string, items: CartItem[]): Promise<Order> {
        const total = items.reduce((sum, item) => sum + item.price * item.qty, 0);
        const order = await this.db.orders.create({
            userId, items, total, status: 'pending',
            createdAt: new Date()
        });
        await this.db.inventory.reserve(items);
        await this.sendConfirmation(order);
        return order;
    }

    private async sendConfirmation(order: Order) {
        this.logger.info(`Sending confirmation for order ${order.id}`);
        // TODO: implement email sending
    }
}''',
            "language": "typescript",
            "filename": "OrderService.ts",
            "agents": ["sec-01", "err-08", "arch-06", "conc-10"],
            "score": 47,
            "created": (now - timedelta(hours=18)).isoformat() + "Z",
            "findings": [
                {"agent": "Concurrency Sage", "severity": "critical", "message": "No transaction wrapping - inventory reserved even if order creation fails", "line": 5},
                {"agent": "Error Philosopher", "severity": "critical", "message": "No rollback on inventory reservation failure", "line": 11},
                {"agent": "Security Sentinel", "severity": "high", "message": "No authorization check - any user can create orders for any userId", "line": 4},
                {"agent": "Architecture Guardian", "severity": "medium", "message": "Business logic directly in service - consider separating payment/order concerns", "line": 5},
                {"agent": "Error Philosopher", "severity": "medium", "message": "TODO comment indicates incomplete implementation in production code", "line": 16},
                {"agent": "Concurrency Sage", "severity": "high", "message": "Race condition: concurrent orders could over-reserve inventory", "line": 11},
            ],
            "tokens_used": 5230,
            "duration_ms": 4120,
        },
    ]

    for sa in sample_analyses:
        aid = str(uuid.uuid4())[:8]
        analyses[aid] = {
            "id": aid,
            "code": sa["code"],
            "language": sa["language"],
            "filename": sa.get("filename", "untitled"),
            "agent_ids": sa["agents"],
            "score": sa["score"],
            "created": sa["created"],
            "findings": sa["findings"],
            "tokens_used": sa["tokens_used"],
            "duration_ms": sa["duration_ms"],
            "status": "completed",
        }

    # Generate daily stats (last 14 days)
    for i in range(14, 0, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        base = random.randint(80_000, 180_000)
        daily_stats.append({
            "date": d,
            "total_tokens": base,
            "analyses": random.randint(30, 90),
            "cost_usd": round(base * 0.000015, 2),
        })

    # Generate hourly stats (last 24 hours)
    for i in range(24, 0, -1):
        h = (now - timedelta(hours=i)).strftime("%H:00")
        hourly_stats.append({
            "hour": h,
            "tokens": random.randint(2000, 18000),
            "analyses": random.randint(1, 8),
        })


_generate_sample_data()


# ──────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    total_tokens = sum(a["tokens_used"] for a in AGENTS)
    total_analyses = len(analyses)
    active_agents = sum(1 for a in AGENTS if a["status"] == "active")
    recent = sorted(analyses.values(), key=lambda x: x["created"], reverse=True)[:5]
    return render_template("dashboard.html",
                           agents=AGENTS,
                           recent_analyses=recent,
                           total_tokens=total_tokens,
                           total_analyses=total_analyses,
                           active_agents=active_agents)


@app.route("/analyze", methods=["GET", "POST"])
def analyze():
    if request.method == "POST":
        code = request.form.get("code", "")
        language = request.form.get("language", "python")
        filename = request.form.get("filename", "untitled")
        selected_agents = request.form.getlist("agents")

        if not selected_agents:
            selected_agents = [a["id"] for a in AGENTS if a["status"] == "active"]

        # Simulate analysis
        aid = str(uuid.uuid4())[:8]
        severity_pool = ["critical", "high", "medium", "low", "info"]
        findings = []
        for agent_id in selected_agents:
            agent = next((a for a in AGENTS if a["id"] == agent_id), None)
            if agent:
                num_findings = random.randint(0, 3)
                for _ in range(num_findings):
                    findings.append({
                        "agent": agent["name"],
                        "severity": random.choice(severity_pool),
                        "message": _random_finding(agent["category"]),
                        "line": random.randint(1, max(1, code.count("\n") + 1)),
                    })

        score = max(10, min(100, 100 - len(findings) * 12 + random.randint(-5, 15)))
        tokens_used = random.randint(2000, 8000)

        analysis = {
            "id": aid,
            "code": code,
            "language": language,
            "filename": filename,
            "agent_ids": selected_agents,
            "score": score,
            "created": datetime.utcnow().isoformat() + "Z",
            "findings": findings,
            "tokens_used": tokens_used,
            "duration_ms": random.randint(1000, 5000),
            "status": "completed",
        }
        analyses[aid] = analysis

        # Update agent stats
        for agent_id in selected_agents:
            agent = next((a for a in AGENTS if a["id"] == agent_id), None)
            if agent:
                agent["tokens_used"] += tokens_used // len(selected_agents)
                agent["total_runs"] += 1
                agent["last_run"] = datetime.utcnow().isoformat() + "Z"

        return redirect(url_for("results", analysis_id=aid))

    return render_template("analyze.html", agents=AGENTS)


@app.route("/results/<analysis_id>")
def results(analysis_id):
    analysis = analyses.get(analysis_id)
    if not analysis:
        return "Analysis not found", 404

    # Group findings by severity
    grouped = {"critical": [], "high": [], "medium": [], "low": [], "info": []}
    for f in analysis["findings"]:
        sev = f.get("severity", "info")
        if sev in grouped:
            grouped[sev].append(f)

    return render_template("results.html", analysis=analysis, grouped=grouped, agents=AGENTS)


@app.route("/agents")
def agents_page():
    return render_template("agents.html", agents=AGENTS)


@app.route("/stats")
def stats_page():
    total_tokens = sum(a["tokens_used"] for a in AGENTS)
    total_cost = round(total_tokens * 0.000015, 2)
    return render_template("stats.html", agents=AGENTS, daily_stats=daily_stats,
                           hourly_stats=hourly_stats, total_tokens=total_tokens,
                           total_cost=total_cost)


# ──────────────────────────────────────────────────────────────
# API endpoints
# ──────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    return jsonify({
        "total_tokens": sum(a["tokens_used"] for a in AGENTS),
        "total_analyses": len(analyses),
        "active_agents": sum(1 for a in AGENTS if a["status"] == "active"),
        "daily_stats": daily_stats,
        "hourly_stats": hourly_stats,
    })


@app.route("/api/agents")
def api_agents():
    return jsonify({"agents": AGENTS})


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

_FINDINGS_BY_CATEGORY = {
    "security": [
        "Potential SQL injection in database query construction",
        "Missing input sanitization on user-provided data",
        "Hardcoded credentials detected in source code",
        "CORS policy allows wildcard origins",
        "JWT token validation missing expiration check",
        "Insecure direct object reference (IDOR) vulnerability",
    ],
    "performance": [
        "N+1 query pattern detected in loop iteration",
        "Missing database index on frequently queried column",
        "Unbounded cache growth without eviction policy",
        "Synchronous I/O blocking in async context",
        "Large payload not paginated - potential memory issue",
        "Redundant computation in hot code path",
    ],
    "style": [
        "Inconsistent naming convention (camelCase vs snake_case)",
        "Function exceeds 50 lines - consider decomposition",
        "Magic number should be extracted to named constant",
        "Unused import detected",
        "Missing type annotations on public API",
    ],
    "testing": [
        "No test coverage for error handling paths",
        "Missing edge case tests for boundary values",
        "Test uses sleep() instead of proper mocking",
        "No integration test for database interactions",
        "Snapshot test needs update after API change",
    ],
    "documentation": [
        "Public API missing docstring with parameter descriptions",
        "Complex algorithm lacks explanatory comments",
        "README missing setup and usage instructions",
        "API endpoint lacks OpenAPI/Swagger documentation",
    ],
    "architecture": [
        "Circular dependency detected between modules",
        "Business logic mixed with presentation layer",
        "God object - class has too many responsibilities",
        "Missing abstraction layer for external service calls",
        "Inconsistent error propagation pattern",
    ],
    "dependencies": [
        "Package has known CVE - update to latest version",
        "Dependency uses deprecated API with removal timeline",
        "Transitive dependency has incompatible license",
        "Pinned version is 3+ major releases behind",
    ],
    "reliability": [
        "No exception handling for network timeout scenarios",
        "Missing retry logic for transient failures",
        "Resource leak: file handle not closed in error path",
        "Unhandled promise rejection in async flow",
        "Circuit breaker missing for external service calls",
    ],
    "types": [
        "Type assertion used instead of proper type narrowing",
        "Nullable type not handled in all code paths",
        "Generic type parameter is unconstrained",
        "Return type should be more specific than 'any'",
    ],
    "concurrency": [
        "Shared mutable state accessed without synchronization",
        "Potential deadlock in nested lock acquisition",
        "Race condition on read-modify-write operation",
        "Thread pool exhaustion under high concurrency",
        "Missing atomic operation for counter increment",
    ],
}


def _random_finding(category):
    pool = _FINDINGS_BY_CATEGORY.get(category, _FINDINGS_BY_CATEGORY["reliability"])
    return random.choice(pool)


# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔬 SYNAPSE Web Dashboard starting on http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
