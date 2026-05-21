"""
SYNAPSE Code Quality Agent
===========================
Analyzes code quality metrics including cyclomatic complexity,
cognitive complexity, maintainability index, code smells,
nesting depth, function length, and comment ratio.

Estimated token consumption: ~15,000 tokens per analysis
  - Prompt (system + code):      ~5,000 tokens
  - Complexity analysis:         ~6,000 tokens
  - Recommendations:             ~4,000 tokens
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class CodeQuality:
    """
    Code quality and complexity analysis agent.

    Computes:
      - Cyclomatic complexity per function
      - Cognitive complexity
      - Maintainability index (Microsoft model)
      - Code smells detection
      - Nesting depth analysis
      - Function/class size metrics
      - Comment ratio analysis

    Token budget: ~15,000 tokens/analysis
    """

    ESTIMATED_TOKENS = 15_000

    # Python / JS / Java / Go control flow keywords that increase complexity
    BRANCH_KEYWORDS = {
        "python":    [r'\bif\b', r'\belif\b', r'\bfor\b', r'\bwhile\b', r'\band\b',
                      r'\bor\b', r'\bexcept\b', r'\bwith\b'],
        "javascript": [r'\bif\b', r'\belse\s+if\b', r'\bfor\b', r'\bwhile\b', r'\b\?\b',
                       r'\b&&\b', r'\b\|\|\b', r'\bcatch\b', r'\bcase\b', r'\bswitch\b'],
        "java":      [r'\bif\b', r'\belse\s+if\b', r'\bfor\b', r'\bwhile\b', r'\b\?\b',
                       r'\b&&\b', r'\b\|\|\b', r'\bcatch\b', r'\bcase\b'],
        "go":        [r'\bif\b', r'\bfor\b', r'\bselect\b', r'\bcase\b', r'\b\&\&\b',
                       r'\b\|\|\b'],
    }

    CODE_SMELL_PATTERNS = [
        (r'def\s+\w+\s*\([^)]*\)\s*:(?:\s*\n(?:\s{4,}.+\n){50,})',
         "Long Method", "Method exceeds 50 lines. Consider extracting sub-functions.", "high"),
        (r'(?:^|\n)(class\s+\w+.*?(?=\nclass|\Z))',
         None, None, None),  # handled separately
        (r'(?:import\s+\*)',
         "Wildcard Import", "Avoid wildcard imports; import specific names.", "medium"),
        (r'(?i)(?:todo|fixme|hack|xxx)\b',
         "TODO/FIXME Marker", "Unresolved TODO/FIXME comment found.", "low"),
        (r'pass\s*$',
         "Empty Block", "Empty pass statement - consider adding implementation or a comment.", "low"),
        (r'except\s*:',
         "Bare Except", "Bare except clause catches all exceptions including KeyboardInterrupt. Catch specific exceptions.", "high"),
        (r'except\s+Exception\s*:',
         "Broad Exception", "Catching generic Exception. Catch specific exception types.", "medium"),
        (r'(?:print\s*\(|console\.log\s*\()',
         "Debug Print", "Debug print/log statement found. Remove before production.", "low"),
        (r'eval\s*\(',
         "Use of eval()", "eval() is dangerous and hard to debug. Avoid when possible.", "high"),
        (r'(?:magic|hardcoded)\s*(?:number|string)',
         "Magic Value", None, "medium"),
    ]

    def __init__(self, config=None):
        self.config = config
        self.name = "code_quality"

    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze code quality metrics and detect code smells."""
        language = context.get("language", self._detect_language(code))
        lines = code.split("\n")

        # ── Line-level Metrics ────────────────────────────────
        total_lines = len(lines)
        blank_lines = sum(1 for l in lines if l.strip() == "")
        comment_lines = self._count_comment_lines(lines, language)
        code_lines = total_lines - blank_lines - comment_lines
        comment_ratio = comment_lines / max(code_lines, 1)

        # ── Function/Class Extraction ─────────────────────────
        functions = self._extract_functions(lines, language)
        classes = self._extract_classes(lines, language)

        func_lengths = [f["length"] for f in functions]
        max_func_length = max(func_lengths) if func_lengths else 0
        avg_func_length = sum(func_lengths) / len(func_lengths) if func_lengths else 0

        # ── Complexity Calculations ───────────────────────────
        cyclomatic = self._cyclomatic_complexity(code, language)
        cognitive = self._cognitive_complexity(code, language)
        max_nesting = self._max_nesting_depth(lines, language)

        # ── Maintainability Index (simplified Microsoft model) ─
        import math
        halstead_volume = code_lines * 2.5  # simplified approximation
        if halstead_volume > 0 and cyclomatic > 0:
            mi = max(0, (171
                - 5.2 * math.log(max(halstead_volume, 1))
                - 0.23 * cyclomatic
                - 16.2 * math.log(max(code_lines, 1))
            ) * 100 / 171)
        else:
            mi = 100.0

        # ── Code Smells ──────────────────────────────────────
        smells = self._detect_smells(code, lines, language, functions, classes)

        # ── Duplicate Detection (simplified) ──────────────────
        duplicates = self._detect_duplicates(lines)

        # ── Build Findings ────────────────────────────────────
        findings: List[Dict[str, Any]] = []

        # Complexity findings
        for func in functions:
            if func["complexity"] > 10:
                sev = "critical" if func["complexity"] > 25 else "high" if func["complexity"] > 15 else "medium"
                findings.append({
                    "category": "Complexity",
                    "title": f"High cyclomatic complexity in '{func['name']}'",
                    "description": f"Cyclomatic complexity is {func['complexity']} (threshold: 10). "
                                   f"Consider splitting into smaller functions.",
                    "severity": sev,
                    "line_number": func["line"],
                    "metric_value": func["complexity"],
                })

        # Nesting findings
        if max_nesting > 4:
            findings.append({
                "category": "Nesting",
                "title": f"Excessive nesting depth: {max_nesting} levels",
                "description": "Deep nesting reduces readability. Use early returns, guard clauses, or extract methods.",
                "severity": "high" if max_nesting > 6 else "medium",
                "metric_value": max_nesting,
            })

        # Function length findings
        for func in functions:
            if func["length"] > 50:
                findings.append({
                    "category": "Function Length",
                    "title": f"Long function '{func['name']}' ({func['length']} lines)",
                    "description": "Functions over 50 lines are hard to test and maintain.",
                    "severity": "medium",
                    "line_number": func["line"],
                })

        # Comment ratio
        if comment_ratio < 0.05 and code_lines > 50:
            findings.append({
                "category": "Documentation",
                "title": "Low comment ratio",
                "description": f"Comment ratio is {comment_ratio:.1%}. Consider adding more documentation.",
                "severity": "low",
                "metric_value": round(comment_ratio, 3),
            })

        # Smells
        for smell in smells:
            findings.append(smell)

        # Duplicate findings
        if duplicates > 0:
            findings.append({
                "category": "Duplication",
                "title": f"{duplicates} duplicate line block(s) detected",
                "description": "Duplicated code increases maintenance burden. Extract common logic.",
                "severity": "medium",
                "metric_value": duplicates,
            })

        # ── Suggestions ──────────────────────────────────────
        suggestions = self._generate_suggestions(
            cyclomatic, cognitive, max_nesting, mi, comment_ratio,
            max_func_length, len(functions), duplicates, smells
        )

        # ── Metrics Dict ─────────────────────────────────────
        metrics = {
            "cyclomatic_complexity": round(cyclomatic, 1),
            "cognitive_complexity": round(cognitive, 1),
            "maintainability_index": round(mi, 1),
            "lines_of_code": total_lines,
            "blank_lines": blank_lines,
            "comment_lines": comment_lines,
            "comment_ratio": round(comment_ratio, 3),
            "function_count": len(functions),
            "class_count": len(classes),
            "max_function_length": max_func_length,
            "avg_function_length": round(avg_func_length, 1),
            "max_nesting_depth": max_nesting,
            "duplicate_line_count": duplicates,
            "code_smells": [s["title"] for s in smells],
        }

        prompt_tokens = max(len(code) // 4, 500) + 1500
        completion_tokens = len(findings) * 150 + 2000

        return {
            "findings": findings,
            "vulnerabilities": [],
            "metrics": metrics,
            "suggestions": suggestions,
            "summary": f"Code quality score: {mi:.0f}/100 | "
                       f"Complexity: {cyclomatic:.0f} | "
                       f"Smells: {len(smells)} | "
                       f"Functions: {len(functions)} | "
                       f"Lines: {total_lines}",
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    # ── Complexity Calculations ────────────────────────────────

    def _cyclomatic_complexity(self, code: str, language: str) -> float:
        """Compute aggregate cyclomatic complexity."""
        lang = language.lower() if language else "python"
        keywords = self.BRANCH_KEYWORDS.get(lang, self.BRANCH_KEYWORDS["python"])
        complexity = 1  # base
        for kw in keywords:
            complexity += len(re.findall(kw, code))
        return complexity

    def _per_function_complexity(self, func_code: str, language: str) -> int:
        """Compute cyclomatic complexity for a single function."""
        lang = language.lower() if language else "python"
        keywords = self.BRANCH_KEYWORDS.get(lang, self.BRANCH_KEYWORDS["python"])
        cc = 1
        for kw in keywords:
            cc += len(re.findall(kw, func_code))
        return cc

    def _cognitive_complexity(self, code: str, language: str) -> float:
        """
        Simplified cognitive complexity: increments on nesting increases
        and break in linear flow.
        """
        lang = language.lower() if language else "python"
        nesting = 0
        total = 0
        lines = code.split("\n")

        indent_unit = self._detect_indent(lines)

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue

            indent = len(line) - len(line.lstrip())
            new_nesting = indent // max(indent_unit, 1)

            # Increment nesting change
            if new_nesting > nesting:
                total += (new_nesting - nesting)
            nesting = new_nesting

            # Control flow keywords
            control_kws = [r'\bif\b', r'\bfor\b', r'\bwhile\b', r'\bexcept\b',
                           r'\belif\b', r'\bcatch\b', r'\bcase\b', r'\bswitch\b']
            for kw in control_kws:
                matches = len(re.findall(kw, stripped))
                total += matches * (1 + nesting)

            # Boolean operators
            total += len(re.findall(r'\b(?:and|or|&&|\|\|)\b', stripped))

        return total

    def _max_nesting_depth(self, lines: List[str], language: str) -> int:
        """Compute maximum indentation nesting depth."""
        max_depth = 0
        indent_unit = self._detect_indent(lines)
        if indent_unit == 0:
            indent_unit = 4

        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                depth = indent // indent_unit
                max_depth = max(max_depth, depth)
        return max_depth

    def _detect_indent(self, lines: List[str]) -> int:
        """Detect indentation unit (2 or 4 spaces)."""
        fours = sum(1 for l in lines if l.strip() and (len(l) - len(l.lstrip())) % 4 == 0 and len(l) - len(l.lstrip()) > 0)
        twos = sum(1 for l in lines if l.strip() and (len(l) - len(l.lstrip())) % 2 == 0 and len(l) - len(l.lstrip()) > 0)
        return 4 if fours >= twos else 2

    # ── Function/Class Extraction ──────────────────────────────

    def _extract_functions(self, lines: List[str], language: str) -> List[Dict]:
        """Extract function definitions with their line numbers and lengths."""
        functions = []
        lang = language.lower() if language else "python"

        if lang == "python":
            pattern = re.compile(r'^(\s*)def\s+(\w+)\s*\(')
        elif lang in ("javascript", "typescript"):
            pattern = re.compile(r'^(\s*)(?:(?:async|function)\s+)?(\w+)\s*(?:=\s*(?:async\s*)?\(|[\(])')
        elif lang == "java":
            pattern = re.compile(r'^(\s*)(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(')
        elif lang == "go":
            pattern = re.compile(r'^(\s*)func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(')
        else:
            pattern = re.compile(r'^(\s*)def\s+(\w+)\s*\(')

        for i, line in enumerate(lines):
            m = pattern.match(line)
            if m:
                indent = len(m.group(1))
                name = m.group(2)
                # Find end of function
                func_lines = [line]
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() == "":
                        func_lines.append(lines[j])
                        continue
                    curr_indent = len(lines[j]) - len(lines[j].lstrip())
                    if curr_indent <= indent and lines[j].strip():
                        break
                    func_lines.append(lines[j])

                func_code = "\n".join(func_lines)
                cc = self._per_function_complexity(func_code, language)

                functions.append({
                    "name": name,
                    "line": i + 1,
                    "length": len(func_lines),
                    "complexity": cc,
                })
        return functions

    def _extract_classes(self, lines: List[str], language: str) -> List[Dict]:
        """Extract class definitions."""
        classes = []
        if language and language.lower() in ("python", "javascript", "typescript", "java"):
            pattern = re.compile(r'^\s*class\s+(\w+)')
        else:
            pattern = re.compile(r'^\s*class\s+(\w+)')

        for i, line in enumerate(lines):
            m = pattern.match(line)
            if m:
                classes.append({"name": m.group(1), "line": i + 1})
        return classes

    # ── Code Smell Detection ───────────────────────────────────

    def _detect_smells(self, code: str, lines: List[str], language: str,
                       functions: List[Dict], classes: List[Dict]) -> List[Dict]:
        """Detect various code smells."""
        smells = []

        # Bare except
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'except\s*:', stripped):
                smells.append({
                    "category": "Code Smell",
                    "title": "Bare except clause",
                    "description": "Bare 'except:' catches all exceptions. Catch specific exceptions.",
                    "severity": "high",
                    "line_number": i + 1,
                })
            elif re.match(r'except\s+Exception\s*:', stripped):
                smells.append({
                    "category": "Code Smell",
                    "title": "Broad exception handler",
                    "description": "Catching generic Exception. Be more specific.",
                    "severity": "medium",
                    "line_number": i + 1,
                })

            # Debug prints
            if re.match(r'(?:print|console\.log|System\.out\.print)', stripped):
                smells.append({
                    "category": "Code Smell",
                    "title": "Debug print statement",
                    "description": "Remove debug print before production.",
                    "severity": "low",
                    "line_number": i + 1,
                })

            # TODO/FIXME
            if re.search(r'(?i)#\s*(?:todo|fixme|hack|xxx)\b', stripped):
                smells.append({
                    "category": "Code Smell",
                    "title": "TODO/FIXME marker",
                    "description": f"Unresolved marker: {stripped[:80]}",
                    "severity": "low",
                    "line_number": i + 1,
                })

        # Long parameter lists
        for func in functions:
            func_line_idx = func["line"] - 1
            if func_line_idx < len(lines):
                match = re.search(r'\(([^)]*)\)', lines[func_line_idx])
                if match:
                    params = [p.strip() for p in match.group(1).split(",") if p.strip()]
                    if len(params) > 5:
                        smells.append({
                            "category": "Code Smell",
                            "title": f"Long parameter list in '{func['name']}'",
                            "description": f"Function has {len(params)} parameters. Consider using a config object or dataclass.",
                            "severity": "medium",
                            "line_number": func["line"],
                        })

        # God class detection
        for cls in classes:
            cls_name = cls["name"]
            method_count = sum(1 for f in functions if True)  # simplified
            if method_count > 20:
                smells.append({
                    "category": "Code Smell",
                    "title": f"God class '{cls_name}'",
                    "description": "Class has too many methods. Consider splitting responsibilities.",
                    "severity": "high",
                    "line_number": cls["line"],
                })

        return smells

    # ── Duplicate Detection ────────────────────────────────────

    def _detect_duplicates(self, lines: List[str]) -> int:
        """Simplified duplicate block detection using consecutive line hashing."""
        window = 4
        seen_hashes = set()
        duplicate_count = 0
        i = 0
        while i <= len(lines) - window:
            block = tuple(l.strip() for l in lines[i:i + window] if l.strip())
            if len(block) >= 3:
                h = hash(block)
                if h in seen_hashes:
                    duplicate_count += 1
                    i += window
                    continue
                seen_hashes.add(h)
            i += 1
        return duplicate_count

    # ── Suggestions ────────────────────────────────────────────

    def _generate_suggestions(self, cyclomatic, cognitive, max_nesting, mi,
                              comment_ratio, max_func_length, func_count,
                              duplicates, smells) -> List[str]:
        suggestions = []
        if cyclomatic > 20:
            suggestions.append("Overall complexity is high. Break down complex functions into smaller, focused units.")
        if cognitive > 30:
            suggestions.append("Cognitive complexity is high. Simplify control flow and reduce nesting.")
        if max_nesting > 4:
            suggestions.append(f"Max nesting depth is {max_nesting}. Use guard clauses and early returns.")
        if mi < 50:
            suggestions.append(f"Maintainability index is {mi:.0f}/100. Refactor for better maintainability.")
        if comment_ratio < 0.05:
            suggestions.append("Add docstrings and inline comments to improve code documentation.")
        if max_func_length > 80:
            suggestions.append("Some functions exceed 80 lines. Extract logical sections into helper functions.")
        if duplicates > 0:
            suggestions.append("Duplicate code blocks detected. Extract shared logic into reusable functions.")
        smell_types = set(s["title"] for s in smells)
        if "Bare except clause" in smell_types:
            suggestions.append("Replace bare except clauses with specific exception types.")
        if not suggestions:
            suggestions.append("Code quality is good. Continue following best practices.")
        return suggestions

    # ── Language Detection ─────────────────────────────────────

    def _detect_language(self, code: str) -> str:
        if re.search(r'\bdef\s+\w+\s*\(.*\)\s*:', code):
            return "python"
        if re.search(r'(?:const|let|var)\s+\w+\s*=', code) or '=>' in code:
            return "javascript"
        if re.search(r'public\s+(?:static\s+)?(?:void|int|String)', code):
            return "java"
        if re.search(r'func\s+\w+\s*\(', code):
            return "go"
        return "python"

    def estimate_tokens(self, code: str) -> int:
        code_tokens = max(len(code) // 4, 500)
        return code_tokens + 2000 + 4000  # prompt + analysis overhead
