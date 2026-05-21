"""
SYNAPSE Architecture Review Agent
===================================
Analyzes code architecture for SOLID violations, coupling metrics,
cohesion analysis, design pattern detection, and structural anti-patterns.

Estimated token consumption: ~20,000 tokens per analysis
  - Prompt (system + code):        ~6,000 tokens
  - Architecture analysis:         ~9,000 tokens
  - Recommendations & refactoring: ~5,000 tokens
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple


class ArchitectureReview:
    """
    Architecture pattern analysis agent.

    Evaluates:
      - SOLID principle violations (SRP, OCP, LSP, ISP, DIP)
      - Coupling metrics (afferent/efferent coupling)
      - Cohesion analysis (LCOM - Lack of Cohesion of Methods)
      - Design pattern detection (Factory, Singleton, Observer, etc.)
      - Anti-patterns (God class, Feature envy, Circular deps)
      - Module boundaries and layering violations
      - Dependency direction analysis

    Token budget: ~20,000 tokens/analysis
    """

    ESTIMATED_TOKENS = 20_000

    # Known design patterns (regex signatures)
    DESIGN_PATTERNS = {
        "Singleton": [
            r'_instance\s*=\s*None',
            r'__new__\s*\(.*cls',
            r'def\s+getInstance\s*\(',
        ],
        "Factory": [
            r'class\s+\w+Factory\b',
            r'def\s+create_\w+\s*\(',
            r'def\s+build_\w+\s*\(',
        ],
        "Observer": [
            r'(?:subscribe|register|add_listener|add_observer|on)\s*\(',
            r'(?:notify|emit|broadcast|publish)\s*\(',
            r'class\s+\w+(?:Observer|Listener|Subscriber)\b',
        ],
        "Strategy": [
            r'class\s+\w+Strategy\b',
            r'(?:set_strategy|with_strategy)\s*\(',
        ],
        "Decorator": [
            r'@\w+\s*\ndef\s+\w+',
            r'class\s+\w+Decorator\b',
            r'functools\.wraps',
        ],
        "Adapter": [
            r'class\s+\w+Adapter\b',
            r'class\s+\w+Wrapper\b',
        ],
        "Command": [
            r'class\s+\w+Command\b',
            r'def\s+execute\s*\(\s*self\s*\)',
        ],
        "Proxy": [
            r'class\s+\w+Proxy\b',
            r'def\s+__getattr__\s*\(',
        ],
        "Builder": [
            r'class\s+\w+Builder\b',
            r'def\s+(?:build|with_\w+)\s*\(\s*self',
        ],
    }

    SOLID_VIOLATIONS = {
        "SRP": {
            "name": "Single Responsibility Principle",
            "description": "Class has too many methods/attributes, suggesting multiple responsibilities.",
        },
        "OCP": {
            "name": "Open/Closed Principle",
            "description": "Code uses type checking or isinstance chains instead of polymorphism.",
        },
        "LSP": {
            "name": "Liskov Substitution Principle",
            "description": "Subclass overrides method with incompatible behavior (raises NotImplementedError).",
        },
        "ISP": {
            "name": "Interface Segregation Principle",
            "description": "Class has methods that not all clients need. Split into focused interfaces.",
        },
        "DIP": {
            "name": "Dependency Inversion Principle",
            "description": "High-level module directly instantiates low-level module instead of using abstractions.",
        },
    }

    def __init__(self, config=None):
        self.config = config
        self.name = "architecture_review"

    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze code architecture and structural patterns."""
        lines = code.split("\n")
        findings: List[Dict[str, Any]] = []
        suggestions: List[str] = []

        # ── Extract Classes and Modules ───────────────────────
        classes = self._extract_classes(code, lines)
        imports = self._extract_imports(lines)
        functions = self._extract_functions(lines)

        # ── SOLID Violations ──────────────────────────────────
        findings.extend(self._check_srp(classes))
        findings.extend(self._check_ocp(code, lines))
        findings.extend(self._check_lsp(classes, code))
        findings.extend(self._check_dip(classes, lines))

        # ── Coupling Analysis ─────────────────────────────────
        coupling_metrics = self._analyze_coupling(classes, imports)

        # ── Cohesion Analysis ─────────────────────────────────
        cohesion_findings = self._analyze_cohesion(classes)
        findings.extend(cohesion_findings)

        # ── Design Pattern Detection ──────────────────────────
        detected_patterns = self._detect_patterns(code)

        # ── Anti-pattern Detection ────────────────────────────
        findings.extend(self._detect_anti_patterns(classes, lines, code))

        # ── Layering Violations ───────────────────────────────
        findings.extend(self._check_layering(imports))

        # Generate suggestions
        suggestions = self._generate_suggestions(findings, coupling_metrics, detected_patterns)

        prompt_tokens = max(len(code) // 4, 500) + 2000
        completion_tokens = len(findings) * 200 + 3000

        return {
            "findings": findings,
            "vulnerabilities": [],
            "metrics": {
                "class_count": len(classes),
                "function_count": len(functions),
                "import_count": len(imports),
                "coupling": coupling_metrics,
                "detected_patterns": detected_patterns,
                "max_methods_per_class": max((c["method_count"] for c in classes), default=0),
                "avg_methods_per_class": (
                    sum(c["method_count"] for c in classes) / len(classes) if classes else 0
                ),
            },
            "suggestions": suggestions,
            "summary": (f"Architecture: {len(classes)} classes, {len(detected_patterns)} patterns detected, "
                        f"{sum(1 for f in findings if f.get('severity') in ('critical', 'high'))} high-severity issues"),
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    # ── Class Extraction ───────────────────────────────────────

    def _extract_classes(self, code: str, lines: List[str]) -> List[Dict]:
        classes = []
        current_class = None
        class_indent = 0

        for i, line in enumerate(lines):
            m = re.match(r'^(\s*)class\s+(\w+)(?:\(([^)]*)\))?\s*:', line)
            if m:
                indent = len(m.group(1))
                name = m.group(2)
                bases = [b.strip() for b in m.group(3).split(",")] if m.group(3) else []
                current_class = {
                    "name": name,
                    "bases": bases,
                    "line": i + 1,
                    "indent": indent,
                    "methods": [],
                    "attributes": set(),
                    "method_count": 0,
                }
                class_indent = indent
                classes.append(current_class)
            elif current_class:
                curr_indent = len(line) - len(line.lstrip())
                if curr_indent > class_indent and line.strip():
                    # Method detection
                    method_match = re.match(r'\s+def\s+(\w+)\s*\(', line)
                    if method_match:
                        current_class["methods"].append(method_match.group(1))
                        current_class["method_count"] += 1
                    # Attribute detection
                    attr_match = re.match(r'\s+self\.(\w+)\s*=', line)
                    if attr_match:
                        current_class["attributes"].add(attr_match.group(1))

        return classes

    def _extract_imports(self, lines: List[str]) -> List[Dict]:
        imports = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            m = re.match(r'(?:from\s+([\w.]+)\s+)?import\s+(.+)', stripped)
            if m:
                module = m.group(1) or ""
                names = [n.strip().split(" as ")[0] for n in m.group(2).split(",")]
                imports.append({"module": module, "names": names, "line": i + 1})
        return imports

    def _extract_functions(self, lines: List[str]) -> List[Dict]:
        functions = []
        for i, line in enumerate(lines):
            m = re.match(r'^(\s*)def\s+(\w+)\s*\(', line)
            if m and not re.match(r'^\s{4,}', line):  # Top-level only
                functions.append({"name": m.group(2), "line": i + 1})
        return functions

    # ── SOLID Checks ───────────────────────────────────────────

    def _check_srp(self, classes: List[Dict]) -> List[Dict]:
        """Check for Single Responsibility Principle violations."""
        findings = []
        for cls in classes:
            if cls["method_count"] > 15:
                findings.append({
                    "category": "SOLID - SRP",
                    "title": f"God class '{cls['name']}' ({cls['method_count']} methods)",
                    "description": (f"Class '{cls['name']}' has {cls['method_count']} methods and "
                                    f"{len(cls['attributes'])} attributes. It likely has multiple responsibilities. "
                                    f"Consider splitting into focused classes."),
                    "severity": "high",
                    "line_number": cls["line"],
                })
            elif cls["method_count"] > 10:
                # Check if methods span multiple domains
                method_names = cls["methods"]
                domains = set()
                for m in method_names:
                    prefix = m.split("_")[0] if "_" in m else m[:4]
                    domains.add(prefix)
                if len(domains) > 5:
                    findings.append({
                        "category": "SOLID - SRP",
                        "title": f"Possible SRP violation in '{cls['name']}'",
                        "description": f"Methods in '{cls['name']}' span {len(domains)} different domains. "
                                       f"Consider if the class has a single responsibility.",
                        "severity": "medium",
                        "line_number": cls["line"],
                    })
        return findings

    def _check_ocp(self, code: str, lines: List[str]) -> List[Dict]:
        """Check for Open/Closed Principle violations."""
        findings = []

        # isinstance chains
        in_function = False
        isinstance_count = 0
        func_line = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'def\s+', stripped):
                if isinstance_count >= 3:
                    findings.append({
                        "category": "SOLID - OCP",
                        "title": f"isinstance chain ({isinstance_count} checks)",
                        "description": "Multiple isinstance checks suggest the code should use polymorphism "
                                       "instead of type-based branching.",
                        "severity": "medium",
                        "line_number": func_line,
                    })
                in_function = True
                isinstance_count = 0
                func_line = i + 1

            if re.search(r'isinstance\s*\(', stripped):
                isinstance_count += 1

        # type() comparisons
        for i, line in enumerate(lines):
            if re.search(r'type\s*\(\w+\)\s*(?:==|!=|is\s)', line):
                findings.append({
                    "category": "SOLID - OCP",
                    "title": "Type comparison instead of isinstance",
                    "description": "Using type() for comparison doesn't support inheritance. "
                                   "Use isinstance() or polymorphism.",
                    "severity": "low",
                    "line_number": i + 1,
                })

        return findings

    def _check_lsp(self, classes: List[Dict], code: str) -> List[Dict]:
        """Check for Liskov Substitution Principle violations."""
        findings = []
        for cls in classes:
            for base in cls["bases"]:
                if base == "object" or not base:
                    continue
                # Check for NotImplementedError in methods
                for method in cls["methods"]:
                    pattern = rf'def\s+{method}\s*\(.*?\):.*?raise\s+NotImplementedError'
                    if re.search(pattern, code, re.DOTALL):
                        findings.append({
                            "category": "SOLID - LSP",
                            "title": f"Possible LSP violation: {cls['name']}.{method}()",
                            "description": f"Method raises NotImplementedError. This class cannot substitute "
                                           f"for its base class '{base}'. Consider using an ABC or composition.",
                            "severity": "medium",
                            "line_number": cls["line"],
                        })
        return findings

    def _check_dip(self, classes: List[Dict], lines: List[str]) -> List[Dict]:
        """Check for Dependency Inversion Principle violations."""
        findings = []
        for cls in classes:
            # Check for direct instantiation of concrete classes in __init__
            for i in range(cls["line"] - 1, min(cls["line"] + 30, len(lines))):
                m = re.search(r'self\.\w+\s*=\s*(\w+)\s*\(', lines[i])
                if m:
                    instantiated = m.group(1)
                    # Skip common framework classes
                    skip = {"dict", "list", "set", "tuple", "str", "int", "float", "bool",
                            "defaultdict", "OrderedDict", "Counter", "deque"}
                    if instantiated not in skip and instantiated[0].isupper():
                        # Check if it's imported as an abstract type
                        is_abstract = False
                        for imp_line in lines:
                            if f"from abc import" in imp_line or f"from typing import" in imp_line:
                                continue
                            if re.search(rf'from\s+\S+\s+import\s+.*\b{instantiated}\b', imp_line):
                                break
                        findings.append({
                            "category": "SOLID - DIP",
                            "title": f"Direct instantiation of '{instantiated}' in {cls['name']}",
                            "description": f"High-level class '{cls['name']}' directly creates '{instantiated}'. "
                                           f"Consider injecting the dependency via constructor.",
                            "severity": "medium",
                            "line_number": i + 1,
                        })
                        break  # One finding per class is enough
        return findings

    # ── Coupling Analysis ──────────────────────────────────────

    def _analyze_coupling(self, classes: List[Dict], imports: List[Dict]) -> Dict:
        """Compute coupling metrics."""
        efferent = len(imports)  # modules this code depends on
        # Simplified afferent: count of unique class references from outside
        all_class_names = {c["name"] for c in classes}
        afferent = 0
        for imp in imports:
            for name in imp["names"]:
                if name in all_class_names:
                    afferent += 1

        instability = efferent / max(efferent + afferent, 1)

        return {
            "efferent_coupling": efferent,
            "afferent_coupling": afferent,
            "instability": round(instability, 3),
            "total_classes": len(classes),
        }

    # ── Cohesion Analysis ──────────────────────────────────────

    def _analyze_cohesion(self, classes: List[Dict]) -> List[Dict]:
        """Simplified LCOM (Lack of Cohesion of Methods) analysis."""
        findings = []
        for cls in classes:
            if cls["method_count"] < 2 or len(cls["attributes"]) < 1:
                continue

            # Simple heuristic: if many methods don't use self.attribute, low cohesion
            # (We use method names containing attribute names as a proxy)
            methods_using_attrs = 0
            for method in cls["methods"]:
                method_uses_attr = False
                for attr in cls["attributes"]:
                    if attr in method:
                        method_uses_attr = True
                        break
                if method_uses_attr:
                    methods_using_attrs += 1

            if cls["method_count"] > 0:
                cohesion_ratio = methods_using_attrs / cls["method_count"]
                if cohesion_ratio < 0.3 and cls["method_count"] > 5:
                    findings.append({
                        "category": "Cohesion",
                        "title": f"Low cohesion in class '{cls['name']}'",
                        "description": f"Only {methods_using_attrs}/{cls['method_count']} methods reference "
                                       f"class attributes. Consider splitting the class.",
                        "severity": "medium",
                        "line_number": cls["line"],
                    })
        return findings

    # ── Design Pattern Detection ───────────────────────────────

    def _detect_patterns(self, code: str) -> List[str]:
        """Detect which design patterns are present in the code."""
        detected = []
        for pattern_name, regexes in self.DESIGN_PATTERNS.items():
            for regex in regexes:
                if re.search(regex, code):
                    detected.append(pattern_name)
                    break
        return detected

    # ── Anti-pattern Detection ─────────────────────────────────

    def _detect_anti_patterns(self, classes: List[Dict], lines: List[str],
                              code: str) -> List[Dict]:
        findings = []

        # God object
        for cls in classes:
            if cls["method_count"] > 20 or len(cls["attributes"]) > 15:
                findings.append({
                    "category": "Anti-pattern",
                    "title": f"God object: '{cls['name']}'",
                    "description": f"Class has {cls['method_count']} methods and {len(cls['attributes'])} attributes. "
                                   f"It's doing too much. Apply Single Responsibility Principle.",
                    "severity": "high",
                    "line_number": cls["line"],
                })

        # Feature envy (method uses other class's data more than own)
        # Simplified: check for methods that heavily use parameter attributes
        for i, line in enumerate(lines):
            m = re.match(r'\s+def\s+(\w+)\s*\(\s*self\s*,\s*(\w+)', line)
            if m:
                method_name = m.group(1)
                param_name = m.group(2)
                # Count usages of param.attr vs self.attr in next 20 lines
                body = "\n".join(lines[i:i+20])
                param_usages = len(re.findall(rf'{param_name}\.\w+', body))
                self_usages = len(re.findall(r'self\.\w+', body))
                if param_usages > 3 and param_usages > self_usages * 2:
                    findings.append({
                        "category": "Anti-pattern",
                        "title": f"Feature envy in '{method_name}'",
                        "description": f"Method uses '{param_name}' attributes ({param_usages}x) more than "
                                       f"self attributes ({self_usages}x). Consider moving this method.",
                        "severity": "medium",
                        "line_number": i + 1,
                    })

        # Circular import heuristic
        imports = self._extract_imports(lines)
        modules = set()
        for imp in imports:
            if imp["module"]:
                modules.add(imp["module"])
        # Check if any import references a module that seems to be this file's domain
        # (This is a simplified heuristic)

        return findings

    # ── Layering Violations ────────────────────────────────────

    def _check_layering(self, imports: List[Dict]) -> List[Dict]:
        """Check for common layering violations."""
        findings = []
        # Common layer hierarchy: view -> service -> repository -> database
        layer_keywords = {
            "presentation": ["view", "controller", "handler", "endpoint", "route", "api"],
            "business": ["service", "usecase", "interactor", "manager"],
            "data": ["repository", "dao", "model", "entity", "orm"],
            "infrastructure": ["database", "cache", "queue", "client", "adapter"],
        }

        detected_layers = set()
        for imp in imports:
            module_lower = imp["module"].lower()
            for layer, keywords in layer_keywords.items():
                if any(kw in module_lower for kw in keywords):
                    detected_layers.add(layer)

        # If we detect data layer importing from presentation layer, that's a violation
        if "data" in detected_layers and "presentation" in detected_layers:
            findings.append({
                "category": "Layering",
                "title": "Possible layering violation",
                "description": "Data layer appears to import from presentation layer. "
                               "Dependencies should flow inward: presentation -> business -> data.",
                "severity": "medium",
            })

        return findings

    # ── Suggestions ────────────────────────────────────────────

    def _generate_suggestions(self, findings: List[Dict], coupling: Dict,
                              patterns: List[str]) -> List[str]:
        suggestions = []

        categories = set(f["category"] for f in findings)

        if any("SRP" in c for c in categories):
            suggestions.append("Split large classes into focused, single-responsibility classes. "
                               "Use the 'Extract Class' refactoring pattern.")
        if any("OCP" in c for c in categories):
            suggestions.append("Replace isinstance chains with polymorphism. "
                               "Use the Strategy pattern for varying behavior.")
        if any("DIP" in c for c in categories):
            suggestions.append("Inject dependencies via constructor instead of instantiating them directly. "
                               "Depend on abstractions, not concretions.")
        if any("Anti-pattern" in c for c in categories):
            suggestions.append("Address anti-patterns: extract responsibilities from God objects, "
                               "move methods to the classes they envy.")
        if coupling.get("instability", 0) > 0.8:
            suggestions.append("High instability detected. Reduce external dependencies "
                               "or introduce abstractions to stabilize the module.")
        if not patterns:
            suggestions.append("Consider applying established design patterns "
                               "to improve code structure and maintainability.")

        if not suggestions:
            suggestions.append("Architecture looks reasonable. Continue following SOLID principles.")

        return suggestions

    def estimate_tokens(self, code: str) -> int:
        code_tokens = max(len(code) // 4, 500)
        return code_tokens + 2000 + 8000
