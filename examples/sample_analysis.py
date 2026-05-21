#!/usr/bin/env python3
"""SYNAPSE Example — Run a full pipeline analysis on a sample Python file.

This script demonstrates how to use SYNAPSE programmatically to analyze
code through the multi-agent pipeline.

Usage:
    python examples/sample_analysis.py
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.refactor_advisor import RefactorAdvisor
from agents.type_checker import TypeChecker
from agents.changelog_generator import ChangelogGenerator


# Sample code to analyze — a small Flask-like API with common issues
SAMPLE_CODE = '''
"""Simple user management API."""

import json
import os
import sqlite3
from datetime import datetime

DATABASE = "users.db"

def get_user(id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
    result = cursor.fetchone()
    conn.close()
    return result

def get_user_by_email(email):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()
    conn.close()
    return result

def create_user(name, email, role):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, role, created_at) VALUES (?, ?, ?, ?)",
        (name, email, role, datetime.now().isoformat())
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id

def delete_user(id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected

def format_user(user):
    if user == None:
        return "No user found"
    return f"User({user[0]}): {user[1]} <{user[2]}> [{user[3]}]"

def calculate_score(value, multiplier=100, bonus=50, threshold=1000):
    adjusted = value * multiplier + bonus
    if adjusted > threshold:
        adjusted = threshold
    return adjusted

def process_items(items):
    results = []
    for i in items:
        if i != None:
            if i > 0:
                if i < 1000:
                    results.append(i * 2)
                else:
                    results.append(1000)
            else:
                results.append(0)
    return results
'''


async def run_analysis():
    """Run SYNAPSE agents on the sample code."""
    print("=" * 60)
    print("  SYNAPSE — Sample Pipeline Analysis")
    print("=" * 60)
    print()

    config = {"provider": "local", "model": "analysis"}
    context = {"file": "sample_api.py", "version": "0.2.0"}

    agents = [
        ("Refactor Advisor", RefactorAdvisor),
        ("Type Checker", TypeChecker),
        ("Changelog Generator", ChangelogGenerator),
    ]

    total_tokens = 0
    all_findings = []
    start_time = time.time()

    for agent_name, AgentClass in agents:
        print(f"▶ Running {agent_name} (~{AgentClass(config).token_estimate:,} tokens)...")
        agent = AgentClass(config)

        result = await agent.analyze(SAMPLE_CODE, context)

        findings = result.get("findings", [])
        metrics = result.get("metrics", {})
        tokens = result.get("tokens_used", 0)
        total_tokens += tokens

        print(f"  ✓ {len(findings)} findings, {tokens:,} tokens")

        # Print top findings
        for finding in findings[:5]:
            severity = finding.get("severity", "info").upper()
            line = finding.get("line", "?")
            msg = finding.get("message", "")
            print(f"    [{severity}] Line {line}: {msg}")

        if len(findings) > 5:
            print(f"    ... and {len(findings) - 5} more findings")

        # Print key metrics
        if metrics:
            print(f"  Metrics:")
            for key, value in metrics.items():
                if key not in ("changelog", "migration_guide"):
                    print(f"    {key}: {value}")

        print()
        all_findings.extend(findings)

    elapsed = time.time() - start_time

    print("=" * 60)
    print(f"  Analysis Complete")
    print(f"  Total findings: {len(all_findings)}")
    print(f"  Total tokens:   {total_tokens:,}")
    print(f"  Time elapsed:   {elapsed:.2f}s")
    print("=" * 60)

    return all_findings


if __name__ == "__main__":
    findings = asyncio.run(run_analysis())
    sys.exit(0 if len(findings) < 50 else 1)
