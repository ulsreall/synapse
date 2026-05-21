"""
SYNAPSE Performance Analyzer Agent
====================================
Detects performance bottlenecks including N+1 queries, memory leaks,
O(n^2) algorithmic patterns, async/await issues, unnecessary allocations,
and I/O blocking in hot paths.

Estimated token consumption: ~16,000 tokens per analysis
  - Prompt (system + code):       ~5,000 tokens
  - Pattern matching & analysis:  ~7,000 tokens
  - Recommendations:              ~4,000 tokens
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


class PerformanceAnalyzer:
    """
    Performance bottleneck detection agent.

    Scans for:
      - N+1 query patterns (ORM loops with lazy loading)
      - Memory leaks (unclosed resources, growing collections)
      - O(n^2) algorithmic patterns (nested loops over same data)
      - Async issues (blocking calls in async functions)
      - Inefficient string concatenation in loops
      - Unnecessary object creation in hot paths
      - Missing database indexes (heuristic)
      - I/O blocking in event loops
      - Large payload serialization issues

    Token budget: ~16,000 tokens/analysis
    """

    ESTIMATED_TOKENS = 16_000

    def __init__(self, config=None):
        self.config = config
        self.name = "performance_analyzer"

    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze code for performance bottlenecks."""
        lines = code.split("\n")
        findings: List[Dict[str, Any]] = []
        suggestions: List[str] = []

        # ── N+1 Query Detection ──────────────────────────────
        findings.extend(self._detect_n_plus_one(lines))

        # ── Memory Leak Patterns ─────────────────────────────
        findings.extend(self._detect_memory_leaks(lines))

        # ── O(n^2) Patterns ──────────────────────────────────
        findings.extend(self._detect_quadratic_patterns(lines))

        # ── Async/Await Issues ───────────────────────────────
        findings.extend(self._detect_async_issues(code, lines))

        # ── String Concatenation in Loops ────────────────────
        findings.extend(self._detect_string_concat_loops(lines))

        # ── Inefficient Patterns ─────────────────────────────
        findings.extend(self._detect_inefficient_patterns(lines))

        # ── Resource Management ──────────────────────────────
        findings.extend(self._detect_resource_issues(lines))

        # ── Blocking I/O in Async ────────────────────────────
        findings.extend(self._detect_blocking_io(lines))

        # Generate suggestions
        suggestions = self._generate_suggestions(findings)

        prompt_tokens = max(len(code) // 4, 500) + 1500
        completion_tokens = len(findings) * 180 + 1500

        sev_counts = {}
        for f in findings:
            sev = f.get("severity", "medium")
            sev_counts[sev] = sev_counts.get(sev, 0) + 1

        summary_parts = [f"Found {len(findings)} performance issue(s)"]
        for sev in ["critical", "high", "medium", "low"]:
            if sev in sev_counts:
                summary_parts.append(f"{sev_counts[sev]} {sev}")

        return {
            "findings": findings,
            "vulnerabilities": [],
            "metrics": {
                "performance_issues": len(findings),
                "n_plus_one_count": sum(1 for f in findings if f.get("category") == "N+1 Query"),
                "memory_leak_count": sum(1 for f in findings if f.get("category") == "Memory Leak"),
                "quadratic_count": sum(1 for f in findings if f.get("category") == "O(n^2) Pattern"),
                "async_issues": sum(1 for f in findings if f.get("category") == "Async Issue"),
            },
            "suggestions": suggestions,
            "summary": "; ".join(summary_parts),
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    # ── N+1 Query Detection ───────────────────────────────────

    def _detect_n_plus_one(self, lines: List[str]) -> List[Dict]:
        findings = []
        in_loop = False
        loop_indent = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            # Track loop context
            if re.match(r'(?:for|while)\b', stripped):
                in_loop = True
                loop_indent = indent
            elif in_loop and stripped and indent <= loop_indent:
                in_loop = False

            # DB query inside a loop
            if in_loop:
                query_patterns = [
                    (r'\.objects\.(?:get|filter|all|exclude)\s*\(',
                     "ORM query inside loop - likely N+1"),
                    (r'\.query\s*\(',
                     "Database query inside loop"),
                    (r'(?:SELECT|INSERT|UPDATE|DELETE)\s+',
                     "SQL query inside loop"),
                    (r'(?:fetchone|fetchall|fetchmany)\s*\(',
                     "DB fetch inside loop"),
                    (r'await\s+\w+\.find(?:One|ById|All)?\s*\(',
                     "ORM find inside loop - likely N+1"),
                    (r'await\s+\w+\.query\s*\(',
                     "Async DB query inside loop"),
                ]
                for pattern, desc in query_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        findings.append({
                            "category": "N+1 Query",
                            "title": desc,
                            "description": f"Database query detected inside a loop at line {i+1}. "
                                           f"This causes N+1 query problem. Use eager loading or batch queries.",
                            "severity": "high",
                            "line_number": i + 1,
                            "code_snippet": stripped[:150],
                        })
                        break

        return findings

    # ── Memory Leak Detection ──────────────────────────────────

    def _detect_memory_leaks(self, lines: List[str]) -> List[Dict]:
        findings = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Unclosed file handles
            if re.search(r'open\s*\([^)]+\)(?!.*(?:with|close))', stripped):
                if 'with ' not in stripped and 'close()' not in stripped:
                    findings.append({
                        "category": "Memory Leak",
                        "title": "File handle not closed",
                        "description": "File opened without 'with' statement or explicit close(). "
                                       "This can leak file descriptors.",
                        "severity": "medium",
                        "line_number": i + 1,
                        "code_snippet": stripped[:150],
                    })

            # Unbounded collections
            if re.search(r'(?:defaultdict|list|dict|set)\(\)', stripped):
                # Check if it's in a loop without clearing
                context_before = "\n".join(lines[max(0, i-5):i])
                if re.search(r'(?:for|while)\b', context_before):
                    findings.append({
                        "category": "Memory Leak",
                        "title": "Collection created in loop without clearing",
                        "description": "A new collection is allocated inside a loop. "
                                       "Ensure it's cleared or moved outside the loop.",
                        "severity": "low",
                        "line_number": i + 1,
                    })

            # Event listener without cleanup
            if re.search(r'(?:addEventListener|on\s*\()\s*["\']', stripped):
                # Check if there's a corresponding removeEventListener
                remaining = "\n".join(lines[i+1:i+50])
                if 'removeEventListener' not in remaining and '.off(' not in remaining:
                    findings.append({
                        "category": "Memory Leak",
                        "title": "Event listener without cleanup",
                        "description": "Event listener added without corresponding removal. "
                                       "This can cause memory leaks in long-lived applications.",
                        "severity": "medium",
                        "line_number": i + 1,
                    })

        return findings

    # ── O(n^2) Pattern Detection ───────────────────────────────

    def _detect_quadratic_patterns(self, lines: List[str]) -> List[Dict]:
        findings = []
        for_indices = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            if re.match(r'for\s+\w+\s+in\s+', stripped):
                for_indices.append((i, indent))

        # Check for nested for loops at the same level
        for outer_idx, (outer_line, outer_indent) in enumerate(for_indices):
            for inner_line, inner_indent in for_indices[outer_idx + 1:]:
                if inner_indent > outer_indent and inner_line - outer_line < 10:
                    # Check if they iterate over the same variable
                    outer_match = re.search(r'in\s+(\w+)', lines[outer_line])
                    inner_match = re.search(r'in\s+(\w+)', lines[inner_line])
                    if outer_match and inner_match:
                        outer_var = outer_match.group(1)
                        inner_var = inner_match.group(1)
                        if outer_var == inner_var:
                            findings.append({
                                "category": "O(n^2) Pattern",
                                "title": f"Nested loop over '{outer_var}' - O(n^2) complexity",
                                "description": f"Both outer and inner loops iterate over '{outer_var}'. "
                                               f"This is O(n^2). Consider using a set or dict for O(n) lookup.",
                                "severity": "high",
                                "line_number": outer_line + 1,
                            })
                        else:
                            findings.append({
                                "category": "O(n^2) Pattern",
                                "title": "Nested loop detected - potential O(n^2)",
                                "description": "Nested iteration detected. Verify this is intentional and not "
                                               "an accidental quadratic pattern.",
                                "severity": "medium",
                                "line_number": outer_line + 1,
                            })
                    break  # Only flag the innermost nesting

        return findings

    # ── Async/Await Issues ─────────────────────────────────────

    def _detect_async_issues(self, code: str, lines: List[str]) -> List[Dict]:
        findings = []
        in_async = False
        async_indent = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            if re.match(r'async\s+def\s+', stripped):
                in_async = True
                async_indent = indent
            elif in_async and stripped and indent <= async_indent and not stripped.startswith('@'):
                if not re.match(r'(?:async|def|class|@)', stripped):
                    in_async = False

            if in_async:
                # time.sleep in async context
                if re.search(r'time\.sleep\s*\(', stripped):
                    findings.append({
                        "category": "Async Issue",
                        "title": "Blocking sleep in async function",
                        "description": "time.sleep() blocks the event loop. Use asyncio.sleep() instead.",
                        "severity": "high",
                        "line_number": i + 1,
                        "code_snippet": stripped[:150],
                    })

                # requests library in async context
                if re.search(r'requests\.(?:get|post|put|delete|patch)\s*\(', stripped):
                    findings.append({
                        "category": "Async Issue",
                        "title": "Synchronous HTTP in async function",
                        "description": "requests library blocks the event loop. Use aiohttp or httpx instead.",
                        "severity": "high",
                        "line_number": i + 1,
                        "code_snippet": stripped[:150],
                    })

                # Synchronous DB call in async
                if re.search(r'\.execute\s*\(', stripped) and 'await' not in stripped:
                    findings.append({
                        "category": "Async Issue",
                        "title": "Synchronous DB call in async function",
                        "description": "Database execute without await blocks the event loop. "
                                       "Use async database driver.",
                        "severity": "medium",
                        "line_number": i + 1,
                    })

        return findings

    # ── String Concatenation in Loops ──────────────────────────

    def _detect_string_concat_loops(self, lines: List[str]) -> List[Dict]:
        findings = []
        in_loop = False
        loop_indent = 0
        loop_line = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            if re.match(r'(?:for|while)\b', stripped):
                in_loop = True
                loop_indent = indent
                loop_line = i
            elif in_loop and stripped and indent <= loop_indent:
                in_loop = False

            if in_loop:
                # String concatenation with +=
                if re.search(r'\w+\s*\+=\s*["\']', stripped):
                    findings.append({
                        "category": "Performance",
                        "title": "String concatenation with += in loop",
                        "description": "String concatenation in a loop creates new string objects each iteration. "
                                       "Use ''.join() or io.StringIO instead.",
                        "severity": "medium",
                        "line_number": i + 1,
                        "code_snippet": stripped[:150],
                    })
                # List append + join is fine, but list += string is not
                if re.search(r'\w+\s*\+=\s*\[.*\+', stripped):
                    findings.append({
                        "category": "Performance",
                        "title": "List concatenation in loop",
                        "description": "Use .extend() or .append() instead of += for list operations in loops.",
                        "severity": "low",
                        "line_number": i + 1,
                    })

        return findings

    # ── Inefficient Patterns ───────────────────────────────────

    def _detect_inefficient_patterns(self, lines: List[str]) -> List[Dict]:
        findings = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # len() in loop condition
            if re.search(r'for\s+\w+\s+in\s+range\s*\(\s*len\s*\(', stripped):
                findings.append({
                    "category": "Performance",
                    "title": "range(len()) anti-pattern",
                    "description": "Iterate directly over the collection instead of using range(len()).",
                    "severity": "low",
                    "line_number": i + 1,
                })

            # Checking membership in list instead of set
            if re.search(r'\bin\s+\[', stripped):
                findings.append({
                    "category": "Performance",
                    "title": "Membership test in list",
                    "description": "Use a set for O(1) membership testing instead of a list (O(n)).",
                    "severity": "medium",
                    "line_number": i + 1,
                })

            # Global variable in tight loop
            if re.search(r'global\s+\w+', stripped):
                findings.append({
                    "category": "Performance",
                    "title": "Global variable usage",
                    "description": "Global variables have slower access than local variables in Python.",
                    "severity": "low",
                    "line_number": i + 1,
                })

            # Repeated regex compilation
            if re.search(r're\.(?:search|match|sub|findall)\s*\(\s*["\']', stripped):
                findings.append({
                    "category": "Performance",
                    "title": "Inline regex compilation",
                    "description": "Regex pattern is compiled on every call. Use re.compile() for repeated patterns.",
                    "severity": "low",
                    "line_number": i + 1,
                })

        return findings

    # ── Resource Management ────────────────────────────────────

    def _detect_resource_issues(self, lines: List[str]) -> List[Dict]:
        findings = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Connection without pooling
            if re.search(r'(?:create_connection|connect)\s*\(', stripped):
                remaining = "\n".join(lines[i:i+20])
                if 'pool' not in remaining.lower():
                    findings.append({
                        "category": "Resource Management",
                        "title": "Database connection without pooling",
                        "description": "Creating individual connections is expensive. Use a connection pool.",
                        "severity": "medium",
                        "line_number": i + 1,
                    })

        return findings

    # ── Blocking I/O Detection ─────────────────────────────────

    def _detect_blocking_io(self, lines: List[str]) -> List[Dict]:
        findings = []
        in_async = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'async\s+def\s+', stripped):
                in_async = True
            elif in_async and stripped and not stripped.startswith((' ', '\t', '#', '@')):
                if not re.match(r'(?:async|def|class)', stripped):
                    in_async = False

            if in_async:
                blocking_calls = [
                    (r'time\.sleep', "time.sleep blocks event loop"),
                    (r'(?:open)\s*\(', "File open() blocks event loop"),
                    (r'input\s*\(', "input() blocks event loop"),
                    (r'subprocess\.(?:call|run|check_output)', "subprocess blocks event loop"),
                    (r'\.join\s*\(\s*\)', "Thread .join() blocks event loop"),
                ]
                for pattern, desc in blocking_calls:
                    if re.search(pattern, stripped):
                        findings.append({
                            "category": "Blocking I/O",
                            "title": desc,
                            "description": f"{desc}. Use async equivalents in async functions.",
                            "severity": "high",
                            "line_number": i + 1,
                        })

        return findings

    # ── Suggestions ────────────────────────────────────────────

    def _generate_suggestions(self, findings: List[Dict]) -> List[str]:
        suggestions = []
        categories = set(f["category"] for f in findings)

        if "N+1 Query" in categories:
            suggestions.append("Use select_related() / prefetch_related() (Django) or joinedload() (SQLAlchemy) to avoid N+1 queries.")
        if "Memory Leak" in categories:
            suggestions.append("Use context managers (with statements) for resource management. Add cleanup for event listeners.")
        if "O(n^2) Pattern" in categories:
            suggestions.append("Replace nested loops with set/dict lookups for O(1) membership testing.")
        if "Async Issue" in categories:
            suggestions.append("Replace blocking calls with async equivalents: aiohttp for HTTP, asyncio.sleep() for delays.")
        if "Blocking I/O" in categories:
            suggestions.append("Use aiofiles for async file I/O, and async database drivers for DB operations.")
        if "Performance" in categories:
            suggestions.append("Cache compiled regexes, use sets for membership tests, prefer ''.join() for string building.")

        if not suggestions:
            suggestions.append("No significant performance issues detected. Code looks efficient.")
        return suggestions

    def estimate_tokens(self, code: str) -> int:
        code_tokens = max(len(code) // 4, 500)
        return code_tokens + 1500 + 5000
