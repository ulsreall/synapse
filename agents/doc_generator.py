"""
SYNAPSE Documentation Generator Agent
=======================================
Generates API documentation, README content, inline comments,
docstrings, and changelog entries from source code analysis.

Estimated token consumption: ~18,000 tokens per analysis
  - Prompt (system + code):     ~6,000 tokens
  - Documentation generation:   ~8,000 tokens
  - API docs & examples:        ~4,000 tokens
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class DocGenerator:
    """
    Documentation generation agent.

    Generates:
      - Function/method docstrings (Google, NumPy, or Sphinx style)
      - API documentation (endpoints, parameters, responses)
      - README structure suggestions
      - Inline comment recommendations
      - Module-level docstrings
      - Type annotation documentation
      - Example usage snippets

    Token budget: ~18,000 tokens/analysis
    """

    ESTIMATED_TOKENS = 18_000

    def __init__(self, config=None):
        self.config = config
        self.name = "doc_generator"

    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze code and generate documentation."""
        lines = code.split("\n")
        language = context.get("language", self._detect_language(code))

        functions = self._extract_functions(lines)
        classes = self._extract_classes(lines)
        modules = self._extract_module_info(lines)

        findings = []
        generated_docs = []

        # ── Check for Missing Docstrings ──────────────────────
        for func in functions:
            if not func["has_docstring"]:
                findings.append({
                    "category": "Documentation",
                    "title": f"Missing docstring for '{func['name']}'",
                    "description": f"Function '{func['name']}' at line {func['line']} has no docstring.",
                    "severity": "low" if not func["is_public"] else "medium",
                    "line_number": func["line"],
                })
                # Generate a docstring
                doc = self._generate_docstring(func, language)
                generated_docs.append(doc)

        for cls in classes:
            if not cls["has_docstring"]:
                findings.append({
                    "category": "Documentation",
                    "title": f"Missing docstring for class '{cls['name']}'",
                    "description": f"Class '{cls['name']}' at line {cls['line']} has no docstring.",
                    "severity": "medium",
                    "line_number": cls["line"],
                })

        # ── Check for Module Docstring ────────────────────────
        if not modules.get("has_module_docstring"):
            findings.append({
                "category": "Documentation",
                "title": "Missing module docstring",
                "description": "Module has no docstring at the top of the file.",
                "severity": "low",
            })

        # ── API Documentation ─────────────────────────────────
        api_docs = self._generate_api_docs(functions, classes)

        # ── README Suggestions ────────────────────────────────
        readme_sections = self._suggest_readme_sections(code, functions, classes)

        # ── Inline Comment Suggestions ────────────────────────
        comment_suggestions = self._suggest_inline_comments(lines, functions)

        for cs in comment_suggestions:
            findings.append(cs)

        # ── Generate Documentation Content ────────────────────
        suggestions = [
            f"Add docstrings to {sum(1 for f in functions if not f['has_docstring'])} undocumented functions.",
            "Use Google-style or NumPy-style docstrings for consistency.",
            "Include type annotations alongside docstrings for better IDE support.",
        ]
        if not modules.get("has_module_docstring"):
            suggestions.append("Add a module-level docstring describing the file's purpose.")

        prompt_tokens = max(len(code) // 4, 500) + 2000
        completion_tokens = len(generated_docs) * 250 + len(findings) * 100 + 2000

        return {
            "findings": findings,
            "vulnerabilities": [],
            "metrics": {
                "total_functions": len(functions),
                "documented_functions": sum(1 for f in functions if f["has_docstring"]),
                "undocumented_functions": sum(1 for f in functions if not f["has_docstring"]),
                "total_classes": len(classes),
                "documented_classes": sum(1 for c in classes if c["has_docstring"]),
                "documentation_coverage": (
                    sum(1 for f in functions if f["has_docstring"]) / max(len(functions), 1) * 100
                ),
            },
            "suggestions": suggestions,
            "summary": (f"Documentation coverage: "
                        f"{sum(1 for f in functions if f['has_docstring'])}/{len(functions)} functions, "
                        f"{sum(1 for c in classes if c['has_docstring'])}/{len(classes)} classes"),
            "generated_docs": generated_docs,
            "api_docs": api_docs,
            "readme_sections": readme_sections,
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    # ── Extraction ─────────────────────────────────────────────

    def _extract_functions(self, lines: List[str]) -> List[Dict]:
        functions = []
        for i, line in enumerate(lines):
            m = re.match(r'^(\s*)(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(.+?))?\s*:', line)
            if m:
                indent = len(m.group(1))
                name = m.group(2)
                params_str = m.group(3) or ""
                return_type = m.group(4).strip() if m.group(4) else None

                # Check for existing docstring
                has_docstring = False
                next_line_idx = i + 1
                while next_line_idx < len(lines) and not lines[next_line_idx].strip():
                    next_line_idx += 1
                if next_line_idx < len(lines):
                    next_stripped = lines[next_line_idx].strip()
                    if next_stripped.startswith('"""') or next_stripped.startswith("'''"):
                        has_docstring = True

                # Parse parameters
                params = []
                for param in params_str.split(","):
                    param = param.strip()
                    if not param or param in ("self", "cls"):
                        continue
                    pname = param.split(":")[0].split("=")[0].strip()
                    phint = None
                    if ":" in param:
                        phint = param.split(":")[1].split("=")[0].strip()
                    params.append({"name": pname, "type_hint": phint})

                functions.append({
                    "name": name,
                    "line": i + 1,
                    "params": params,
                    "return_type": return_type,
                    "has_docstring": has_docstring,
                    "is_public": not name.startswith("_"),
                    "is_async": "async" in line,
                    "is_method": indent > 0,
                    "indent": indent,
                })
        return functions

    def _extract_classes(self, lines: List[str]) -> List[Dict]:
        classes = []
        for i, line in enumerate(lines):
            m = re.match(r'^\s*class\s+(\w+)(?:\(([^)]*)\))?\s*:', line)
            if m:
                has_docstring = False
                next_line_idx = i + 1
                while next_line_idx < len(lines) and not lines[next_line_idx].strip():
                    next_line_idx += 1
                if next_line_idx < len(lines):
                    ns = lines[next_line_idx].strip()
                    if ns.startswith('"""') or ns.startswith("'''"):
                        has_docstring = True
                classes.append({
                    "name": m.group(1),
                    "line": i + 1,
                    "has_docstring": has_docstring,
                })
        return classes

    def _extract_module_info(self, lines: List[str]) -> Dict:
        has_module_docstring = False
        if lines:
            first_code = ""
            for line in lines:
                if line.strip() and not line.strip().startswith("#"):
                    first_code = line.strip()
                    break
            if first_code.startswith('"""') or first_code.startswith("'''"):
                has_module_docstring = True
        return {"has_module_docstring": has_module_docstring}

    # ── Docstring Generation ───────────────────────────────────

    def _generate_docstring(self, func: Dict, language: str) -> Dict:
        """Generate a Google-style docstring for a function."""
        indent = " " * (func.get("indent", 0) + 4)
        lines = []

        # Summary line
        name = func["name"]
        summary = self._infer_summary(name)
        lines.append(f'{indent}"""')
        lines.append(f'{indent}{summary}')
        lines.append(f'{indent}')

        # Args section
        if func["params"]:
            lines.append(f'{indent}Args:')
            for p in func["params"]:
                type_str = f" ({p['type_hint']})" if p.get("type_hint") else ""
                lines.append(f'{indent}    {p["name"]}{type_str}: Description of {p["name"]}.')

        # Returns section
        if func.get("return_type") and func["return_type"] != "None":
            lines.append(f'{indent}')
            lines.append(f'{indent}Returns:')
            lines.append(f'{indent}    {func["return_type"]}: Description of return value.')

        # Raises section
        lines.append(f'{indent}')
        lines.append(f'{indent}Raises:')
        lines.append(f'{indent}    ValueError: If input is invalid.')
        lines.append(f'{indent}"""')

        return {
            "function": func["name"],
            "line": func["line"],
            "docstring": "\n".join(lines),
            "style": "google",
        }

    def _infer_summary(self, func_name: str) -> str:
        """Infer a docstring summary from the function name."""
        # Convert snake_case to sentence
        words = func_name.replace("_", " ").strip()
        # Common prefixes
        if words.startswith("get "):
            return f"Retrieve {words[4:]}."
        elif words.startswith("set "):
            return f"Set {words[4:]}."
        elif words.startswith("is "):
            return f"Check if {words[3:]}."
        elif words.startswith("has "):
            return f"Check if has {words[4:]}."
        elif words.startswith("create "):
            return f"Create a new {words[7:]}."
        elif words.startswith("delete "):
            return f"Delete {words[7:]}."
        elif words.startswith("update "):
            return f"Update {words[7:]}."
        elif words.startswith("find "):
            return f"Find {words[5:]}."
        elif words.startswith("validate "):
            return f"Validate {words[9:]}."
        elif words.startswith("parse "):
            return f"Parse {words[6:]}."
        elif words.startswith("build "):
            return f"Build {words[6:]}."
        elif words.startswith("calculate "):
            return f"Calculate {words[10:]}."
        elif words.startswith("process "):
            return f"Process {words[8:]}."
        else:
            return f"{words.capitalize()}."

    # ── API Documentation ──────────────────────────────────────

    def _generate_api_docs(self, functions: List[Dict], classes: List[Dict]) -> List[Dict]:
        """Generate API documentation entries."""
        api_docs = []

        for func in functions:
            if func["is_public"]:
                entry = {
                    "name": func["name"],
                    "type": "async function" if func["is_async"] else "function",
                    "line": func["line"],
                    "parameters": [
                        {"name": p["name"], "type": p.get("type_hint", "Any")}
                        for p in func["params"]
                    ],
                    "returns": func.get("return_type", "None"),
                }
                api_docs.append(entry)

        for cls in classes:
            entry = {
                "name": cls["name"],
                "type": "class",
                "line": cls["line"],
            }
            api_docs.append(entry)

        return api_docs

    # ── README Suggestions ─────────────────────────────────────

    def _suggest_readme_sections(self, code: str, functions: List[Dict],
                                  classes: List[Dict]) -> List[str]:
        """Suggest README sections based on code analysis."""
        sections = [
            "# Project Name",
            "## Description\n<!-- Describe what this project does -->",
            "## Installation\n```bash\npip install -r requirements.txt\n```",
        ]

        # Add API section if there are public functions
        public_funcs = [f for f in functions if f["is_public"]]
        if public_funcs:
            sections.append("## API Reference")
            for func in public_funcs[:10]:  # Limit to 10
                params = ", ".join(f"{p['name']}: {p.get('type_hint', 'Any')}" for p in func["params"])
                ret = func.get("return_type", "None")
                sections.append(f"- `{func['name']}({params}) -> {ret}`")

        if any(c["name"].endswith("Error") or c["name"].endswith("Exception") for c in classes):
            sections.append("## Error Handling\n<!-- Document custom exceptions -->")

        sections.append("## Usage\n```python\n# Example usage\n```")
        sections.append("## Testing\n```bash\npytest\n```")
        sections.append("## License\n<!-- Add license -->")

        return sections

    # ── Inline Comment Suggestions ─────────────────────────────

    def _suggest_inline_comments(self, lines: List[str], functions: List[Dict]) -> List[Dict]:
        """Suggest where inline comments would help."""
        findings = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue

            # Complex expressions without comments
            if len(stripped) > 100:
                # Long line might need explanation
                prev_line = lines[i-1].strip() if i > 0 else ""
                if not prev_line.startswith("#"):
                    findings.append({
                        "category": "Documentation",
                        "title": "Long line without comment",
                        "description": f"Line {i+1} is {len(stripped)} chars. Consider adding an inline comment.",
                        "severity": "info",
                        "line_number": i + 1,
                    })

            # Magic numbers
            if re.search(r'(?<!\w)(?:0x[0-9a-fA-F]+|[2-9]\d{2,}|[1-9]\d{3,})(?!\w)', stripped):
                if not stripped.startswith("#"):
                    findings.append({
                        "category": "Documentation",
                        "title": "Magic number",
                        "description": f"Numeric literal at line {i+1} should have a comment explaining its meaning.",
                        "severity": "info",
                        "line_number": i + 1,
                    })

        return findings[:20]  # Limit findings

    def _detect_language(self, code: str) -> str:
        if re.search(r'\bdef\s+\w+\s*\(.*\)\s*:', code):
            return "python"
        return "python"

    def estimate_tokens(self, code: str) -> int:
        code_tokens = max(len(code) // 4, 500)
        return code_tokens + 2000 + 8000
