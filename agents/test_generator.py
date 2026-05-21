"""
SYNAPSE Test Generator Agent
==============================
Generates test cases including unit tests, integration tests,
edge case analysis, mocking strategies, and test fixtures.

Estimated token consumption: ~22,000 tokens per analysis
  - Prompt (system + code):    ~6,000 tokens
  - Test case generation:      ~10,000 tokens
  - Edge case analysis:        ~4,000 tokens
  - Mocking strategies:        ~2,000 tokens
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class TestGenerator:
    """
    Test case generation agent.

    Analyzes code and generates:
      - Unit test skeletons for each function/method
      - Edge case identification (null, empty, boundary, overflow)
      - Integration test suggestions
      - Mocking strategies for external dependencies
      - Test fixture recommendations
      - Parameterized test cases
      - Error/exception path tests

    Token budget: ~22,000 tokens/analysis (highest in pipeline)
    """

    ESTIMATED_TOKENS = 22_000

    # Type to test value mappings
    TYPE_TEST_VALUES = {
        "int":     ["0", "1", "-1", "sys.maxsize", "-sys.maxsize - 1"],
        "float":   ["0.0", "1.5", "-1.5", "float('inf')", "float('nan')"],
        "str":     ['""', '"test"', '"a" * 10000', '"\\n\\t"', '"unicode: café"'],
        "bool":    ["True", "False"],
        "list":    ["[]", "[1]", "[1, 2, 3]", "list(range(10000))"],
        "dict":    ["{}", '{"key": "value"}', '{"a": {"b": {"c": 1}}}'],
        "tuple":   ["()", "(1,)", "(1, 2, 3)"],
        "set":     ["set()", "{1}", "{1, 2, 3}"],
        "bytes":   ["b''", "b'test'"],
        "None":    ["None"],
        "Optional":["None", "value"],
    }

    def __init__(self, config=None):
        self.config = config
        self.name = "test_generator"

    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze code and generate comprehensive test cases."""
        lines = code.split("\n")
        language = context.get("language", self._detect_language(code))

        # ── Extract Functions & Methods ───────────────────────
        functions = self._extract_functions(lines)

        # ── Extract Classes ───────────────────────────────────
        classes = self._extract_classes(lines)

        # ── Extract Imports ───────────────────────────────────
        imports = self._extract_imports(lines)

        # ── Generate Tests ────────────────────────────────────
        generated_tests = []
        edge_cases = []
        mock_suggestions = []

        for func in functions:
            # Generate test cases for each function
            tests = self._generate_function_tests(func, language)
            generated_tests.extend(tests)

            # Identify edge cases
            ec = self._identify_edge_cases(func)
            edge_cases.extend(ec)

            # Identify mocking needs
            mocks = self._identify_mock_needs(func, imports)
            mock_suggestions.extend(mocks)

        for cls in classes:
            # Generate class-level tests
            class_tests = self._generate_class_tests(cls, language)
            generated_tests.extend(class_tests)

        # ── Build Findings ────────────────────────────────────
        findings = []

        if not functions and not classes:
            findings.append({
                "category": "Test Coverage",
                "title": "No testable units found",
                "description": "No functions or classes found to generate tests for.",
                "severity": "low",
            })

        for func in functions:
            if not self._has_existing_tests(func["name"], code):
                findings.append({
                    "category": "Test Coverage",
                    "title": f"Missing tests for '{func['name']}'",
                    "description": f"Function '{func['name']}' at line {func['line']} has no apparent test coverage.",
                    "severity": "medium",
                    "line_number": func["line"],
                })

        if edge_cases:
            findings.append({
                "category": "Edge Cases",
                "title": f"{len(edge_cases)} edge case(s) identified for testing",
                "description": "Boundary conditions and edge cases that should be tested.",
                "severity": "medium",
            })

        # ── Generate Test Code ────────────────────────────────
        test_code = self._render_test_code(generated_tests, language)

        suggestions = []
        if functions:
            suggestions.append("Add generated test cases to your test suite.")
        if mock_suggestions:
            suggestions.append("Set up mocks for external dependencies before running integration tests.")
        if edge_cases:
            suggestions.append("Pay special attention to boundary conditions and error paths.")
        suggestions.append("Aim for >80% code coverage with a mix of unit and integration tests.")

        prompt_tokens = max(len(code) // 4, 500) + 2000
        completion_tokens = len(generated_tests) * 300 + len(edge_cases) * 100 + 2000

        return {
            "findings": findings,
            "vulnerabilities": [],
            "metrics": {
                "functions_found": len(functions),
                "classes_found": len(classes),
                "tests_generated": len(generated_tests),
                "edge_cases_found": len(edge_cases),
                "mock_suggestions": len(mock_suggestions),
            },
            "suggestions": suggestions,
            "summary": (f"Generated {len(generated_tests)} test cases for "
                        f"{len(functions)} functions, {len(edge_cases)} edge cases identified"),
            "generated_tests": generated_tests,
            "test_code": test_code,
            "edge_cases": edge_cases,
            "mock_suggestions": mock_suggestions,
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    # ── Function Extraction ────────────────────────────────────

    def _extract_functions(self, lines: List[str]) -> List[Dict]:
        functions = []
        for i, line in enumerate(lines):
            # Python function
            m = re.match(r'^(\s*)(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(.+))?\s*:', line)
            if m:
                indent = len(m.group(1))
                name = m.group(2)
                params_str = m.group(3)
                return_type = m.group(4).strip() if m.group(4) else None
                params = self._parse_params(params_str)
                functions.append({
                    "name": name,
                    "line": i + 1,
                    "params": params,
                    "return_type": return_type,
                    "is_async": "async" in line,
                    "is_method": indent > 0,
                    "body_start": i + 1,
                })

        # Compute body for each function
        for idx, func in enumerate(functions):
            start = func["body_start"] - 1
            func_indent = len(lines[start]) - len(lines[start].lstrip()) if start < len(lines) else 0
            end = len(lines)
            if idx + 1 < len(functions):
                end = functions[idx + 1]["body_start"] - 1
            body_lines = lines[start:end]
            func["body"] = "\n".join(body_lines)
            func["body_length"] = len(body_lines)

        return functions

    def _extract_classes(self, lines: List[str]) -> List[Dict]:
        classes = []
        for i, line in enumerate(lines):
            m = re.match(r'^\s*class\s+(\w+)(?:\(([^)]*)\))?\s*:', line)
            if m:
                classes.append({
                    "name": m.group(1),
                    "bases": [b.strip() for b in m.group(2).split(",")] if m.group(2) else [],
                    "line": i + 1,
                })
        return classes

    def _extract_imports(self, lines: List[str]) -> List[str]:
        imports = []
        for line in lines:
            stripped = line.strip()
            if re.match(r'(?:from\s+\S+\s+)?import\s+', stripped):
                imports.append(stripped)
        return imports

    def _parse_params(self, params_str: str) -> List[Dict]:
        """Parse function parameters into structured data."""
        params = []
        if not params_str or not params_str.strip():
            return params

        for param in params_str.split(","):
            param = param.strip()
            if not param or param in ("self", "cls"):
                continue

            name = param
            type_hint = None
            default = None

            # Check for default value
            if "=" in param:
                name_part, default = param.split("=", 1)
                name = name_part.strip()
                default = default.strip()

            # Check for type hint
            if ":" in name:
                name_part, type_hint = name.split(":", 1)
                name = name_part.strip()
                type_hint = type_hint.strip()

            params.append({
                "name": name,
                "type": type_hint,
                "default": default,
                "has_default": default is not None,
            })
        return params

    # ── Test Generation ────────────────────────────────────────

    def _generate_function_tests(self, func: Dict, language: str) -> List[Dict]:
        """Generate test cases for a function."""
        tests = []

        # Happy path test
        test_args = self._generate_happy_path_args(func["params"])
        tests.append({
            "function": func["name"],
            "test_name": f"test_{func['name']}_happy_path",
            "type": "unit",
            "description": f"Test {func['name']} with normal valid inputs",
            "args": test_args,
            "line_ref": func["line"],
        })

        # Edge case tests for each parameter
        for param in func["params"]:
            edge_values = self._get_edge_values(param)
            for ev in edge_values:
                tests.append({
                    "function": func["name"],
                    "test_name": f"test_{func['name']}_{param['name']}_{ev['label']}",
                    "type": "edge_case",
                    "description": f"Test {func['name']} with {param['name']}={ev['description']}",
                    "args": {param["name"]: ev["value"]},
                    "expected": ev.get("expected", "depends on implementation"),
                    "line_ref": func["line"],
                })

        # Error/exception tests
        if self._might_raise(func):
            tests.append({
                "function": func["name"],
                "test_name": f"test_{func['name']}_raises_on_invalid_input",
                "type": "error",
                "description": f"Test that {func['name']} raises appropriate exception on invalid input",
                "args": {},
                "expected_exception": "ValueError or TypeError",
                "line_ref": func["line"],
            })

        # Type error tests
        for param in func["params"]:
            if param["type"]:
                tests.append({
                    "function": func["name"],
                    "test_name": f"test_{func['name']}_{param['name']}_wrong_type",
                    "type": "error",
                    "description": f"Test {func['name']} with wrong type for {param['name']}",
                    "args": {param["name"]: '"invalid_type"'},
                    "expected_exception": "TypeError",
                    "line_ref": func["line"],
                })

        return tests

    def _generate_class_tests(self, cls: Dict, language: str) -> List[Dict]:
        """Generate class-level test cases."""
        tests = []

        # Instantiation test
        tests.append({
            "function": cls["name"],
            "test_name": f"test_{cls['name']}_init",
            "type": "unit",
            "description": f"Test that {cls['name']} can be instantiated",
            "line_ref": cls["line"],
        })

        # String representation
        tests.append({
            "function": cls["name"],
            "test_name": f"test_{cls['name']}_repr",
            "type": "unit",
            "description": f"Test string representation of {cls['name']}",
            "line_ref": cls["line"],
        })

        return tests

    # ── Edge Case Identification ───────────────────────────────

    def _identify_edge_cases(self, func: Dict) -> List[Dict]:
        """Identify edge cases that should be tested."""
        edge_cases = []

        for param in func["params"]:
            name = param["name"]
            ptype = param["type"]

            if ptype:
                type_lower = ptype.lower()
                if "int" in type_lower:
                    edge_cases.append({
                        "function": func["name"],
                        "param": name,
                        "case": "zero",
                        "description": f"Test {name}=0",
                    })
                    edge_cases.append({
                        "function": func["name"],
                        "param": name,
                        "case": "negative",
                        "description": f"Test {name}=-1 (negative value)",
                    })
                    edge_cases.append({
                        "function": func["name"],
                        "param": name,
                        "case": "max_int",
                        "description": f"Test {name}=sys.maxsize (boundary)",
                    })

                if "str" in type_lower:
                    edge_cases.append({
                        "function": func["name"],
                        "param": name,
                        "case": "empty_string",
                        "description": f"Test {name}='' (empty string)",
                    })
                    edge_cases.append({
                        "function": func["name"],
                        "param": name,
                        "case": "whitespace",
                        "description": f"Test {name}='   ' (whitespace only)",
                    })
                    edge_cases.append({
                        "function": func["name"],
                        "param": name,
                        "case": "unicode",
                        "description": f"Test {name} with unicode characters",
                    })

                if "list" in type_lower or "sequence" in type_lower:
                    edge_cases.append({
                        "function": func["name"],
                        "param": name,
                        "case": "empty_list",
                        "description": f"Test {name}=[] (empty list)",
                    })
                    edge_cases.append({
                        "function": func["name"],
                        "param": name,
                        "case": "single_element",
                        "description": f"Test {name}=[single] (single element)",
                    })

            # Name-based heuristics
            if "password" in name.lower() or "secret" in name.lower():
                edge_cases.append({
                    "function": func["name"],
                    "param": name,
                    "case": "special_chars",
                    "description": f"Test {name} with special characters",
                })

            if "url" in name.lower() or "path" in name.lower():
                edge_cases.append({
                    "function": func["name"],
                    "param": name,
                    "case": "malformed",
                    "description": f"Test {name} with malformed input",
                })

        return edge_cases

    # ── Mock Identification ────────────────────────────────────

    def _identify_mock_needs(self, func: Dict, imports: List[str]) -> List[Dict]:
        """Identify what needs to be mocked for testing."""
        mocks = []
        body = func.get("body", "")

        # Database calls
        if re.search(r'(?:\.objects\.|\.query|\.execute|\.find|\.save|\.create|\.delete)', body):
            mocks.append({
                "function": func["name"],
                "mock_target": "database",
                "description": f"Mock database operations in {func['name']}",
            })

        # HTTP calls
        if re.search(r'(?:requests\.(?:get|post)|aiohttp|httpx|fetch\(|axios)', body):
            mocks.append({
                "function": func["name"],
                "mock_target": "http_client",
                "description": f"Mock HTTP client in {func['name']}",
            })

        # File I/O
        if re.search(r'(?:open\s*\(|readFile|writeFile|\.read\(\)|\.write\()', body):
            mocks.append({
                "function": func["name"],
                "mock_target": "filesystem",
                "description": f"Mock file operations in {func['name']}",
            })

        # External services
        if re.search(r'(?:redis|celery|boto3|s3|sendgrid|twilio)', body):
            mocks.append({
                "function": func["name"],
                "mock_target": "external_service",
                "description": f"Mock external service calls in {func['name']}",
            })

        # Time-dependent
        if re.search(r'(?:datetime\.now|time\.time|time\.sleep)', body):
            mocks.append({
                "function": func["name"],
                "mock_target": "time",
                "description": f"Mock time functions in {func['name']}",
            })

        return mocks

    # ── Test Code Rendering ────────────────────────────────────

    def _render_test_code(self, tests: List[Dict], language: str) -> str:
        """Render generated tests into executable test code."""
        if not tests:
            return "# No tests generated"

        lines = [
            '"""',
            'Auto-generated tests by SYNAPSE Test Generator',
            '"""',
            'import pytest',
            '',
        ]

        # Group tests by function
        by_func: Dict[str, List[Dict]] = {}
        for t in tests:
            func = t["function"]
            if func not in by_func:
                by_func[func] = []
            by_func[func].append(t)

        for func_name, func_tests in by_func.items():
            lines.append(f'# Tests for {func_name}')
            lines.append('')

            for t in func_tests:
                if t.get("type") == "error" and t.get("expected_exception"):
                    lines.append(f'async def {t["test_name"]}():' if False else f'def {t["test_name"]}():')
                    lines.append(f'    """{t["description"]}"""')
                    lines.append(f'    with pytest.raises({t["expected_exception"].split(" or ")[0].strip()}):')
                    args_str = ", ".join(f"{k}={v}" for k, v in t.get("args", {}).items()) if t.get("args") else "None"
                    lines.append(f'        {func_name}({args_str})')
                else:
                    lines.append(f'def {t["test_name"]}():')
                    lines.append(f'    """{t["description"]}"""')
                    if t.get("args"):
                        for arg_name, arg_val in t["args"].items():
                            lines.append(f'    {arg_name} = {arg_val}')
                        args_str = ", ".join(t["args"].keys())
                        lines.append(f'    result = {func_name}({args_str})')
                    else:
                        lines.append(f'    result = {func_name}()')
                    lines.append(f'    assert result is not None  # TODO: Add assertion')
                lines.append('')
                lines.append('')

        return "\n".join(lines)

    # ── Helpers ────────────────────────────────────────────────

    def _generate_happy_path_args(self, params: List[Dict]) -> Dict[str, str]:
        """Generate reasonable test arguments for the happy path."""
        args = {}
        for p in params:
            if p["has_default"]:
                continue  # Use default
            if p["type"]:
                t = p["type"].lower()
                if "int" in t:
                    args[p["name"]] = "42"
                elif "float" in t:
                    args[p["name"]] = "3.14"
                elif "str" in t:
                    args[p["name"]] = '"test_value"'
                elif "bool" in t:
                    args[p["name"]] = "True"
                elif "list" in t:
                    args[p["name"]] = "[1, 2, 3]"
                elif "dict" in t:
                    args[p["name"]] = '{"key": "value"}'
                else:
                    args[p["name"]] = "None"
            else:
                # Infer from name
                name = p["name"].lower()
                if "count" in name or "num" in name or "size" in name or "length" in name:
                    args[p["name"]] = "10"
                elif "name" in name or "title" in name or "label" in name:
                    args[p["name"]] = '"test_name"'
                elif "flag" in name or "is_" in name or "has_" in name:
                    args[p["name"]] = "True"
                elif "items" in name or "data" in name or "values" in name:
                    args[p["name"]] = "[1, 2, 3]"
                else:
                    args[p["name"]] = "None"
        return args

    def _get_edge_values(self, param: Dict) -> List[Dict]:
        """Get edge case values for a parameter."""
        edges = []
        ptype = (param.get("type") or "").lower()
        name = param["name"].lower()

        if "int" in ptype or "count" in name or "num" in name:
            edges.extend([
                {"label": "zero", "value": "0", "description": "zero", "expected": "depends"},
                {"label": "negative", "value": "-1", "description": "negative value", "expected": "error or handle"},
                {"label": "large", "value": "10**9", "description": "very large value", "expected": "depends"},
            ])
        elif "str" in ptype or "name" in name:
            edges.extend([
                {"label": "empty", 'value': '""', "description": "empty string", "expected": "depends"},
                {"label": "whitespace", 'value': '"   "', "description": "whitespace-only", "expected": "depends"},
                {"label": "long", 'value': '"x" * 10000', "description": "very long string", "expected": "depends"},
            ])
        elif "list" in ptype or "items" in name:
            edges.extend([
                {"label": "empty", "value": "[]", "description": "empty list", "expected": "depends"},
                {"label": "single", "value": "[1]", "description": "single element", "expected": "depends"},
            ])
        else:
            edges.append({"label": "none", "value": "None", "description": "None value", "expected": "error or handle"})

        return edges

    def _might_raise(self, func: Dict) -> bool:
        """Check if function body contains raise statements or assertions."""
        body = func.get("body", "")
        return bool(re.search(r'\b(?:raise|assert)\b', body))

    def _has_existing_tests(self, func_name: str, code: str) -> bool:
        """Heuristic: check if tests for this function exist in the code."""
        test_pattern = rf'def\s+test_.*{re.escape(func_name)}'
        return bool(re.search(test_pattern, code))

    def _detect_language(self, code: str) -> str:
        if re.search(r'\bdef\s+\w+\s*\(.*\)\s*:', code):
            return "python"
        return "python"

    def estimate_tokens(self, code: str) -> int:
        code_tokens = max(len(code) // 4, 500)
        return code_tokens + 2000 + 10000
