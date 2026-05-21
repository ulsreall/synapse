"""
SYNAPSE Dependency Audit Agent
================================
Audits project dependencies for known vulnerabilities (CVEs),
license compatibility issues, outdated packages, and supply chain risks.

Estimated token consumption: ~12,000 tokens per analysis
  - Prompt (system + code):       ~4,000 tokens
  - Dependency analysis:          ~5,000 tokens
  - CVE & license checking:       ~3,000 tokens
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set


class DependencyAudit:
    """
    Dependency vulnerability and license audit agent.

    Analyzes:
      - Known vulnerable packages (CVE pattern matching)
      - License compatibility issues
      - Outdated package versions
      - Transitive dependency risks
      - Supply chain security indicators
      - Pinned vs unpinned versions
      - Dev dependencies in production

    Token budget: ~12,000 tokens/analysis
    """

    ESTIMATED_TOKENS = 12_000

    # Known vulnerable package versions (simplified database)
    KNOWN_VULNERABILITIES = {
        "requests": [
            {"below": "2.31.0", "cve": "CVE-2023-32681", "severity": "medium",
             "title": "Unintended leak of Proxy-Authorization header"},
        ],
        "flask": [
            {"below": "2.3.2", "cve": "CVE-2023-30861", "severity": "high",
             "title": "Cookie handling vulnerability"},
        ],
        "django": [
            {"below": "4.2.3", "cve": "CVE-2023-36053", "severity": "high",
             "title": "ReDoS via EmailValidator/URLValidator"},
            {"below": "3.2.20", "cve": "CVE-2023-36053", "severity": "high",
             "title": "ReDoS via validators"},
        ],
        "pillow": [
            {"below": "10.0.0", "cve": "CVE-2023-44271", "severity": "high",
             "title": "Denial of service via image processing"},
        ],
        "pyyaml": [
            {"below": "6.0.1", "cve": "CVE-2020-14343", "severity": "critical",
             "title": "Arbitrary code execution via yaml.load"},
        ],
        "urllib3": [
            {"below": "1.26.17", "cve": "CVE-2023-45803", "severity": "medium",
             "title": "Request body not stripped on redirect"},
            {"below": "1.26.18", "cve": "CVE-2023-43804", "severity": "medium",
             "title": "Cookie header not stripped on cross-origin redirect"},
        ],
        "cryptography": [
            {"below": "41.0.3", "cve": "CVE-2023-38325", "severity": "medium",
             "title": "Memory corruption in PKCS12 serialization"},
        ],
        "setuptools": [
            {"below": "65.5.1", "cve": "CVE-2022-40897", "severity": "medium",
             "title": "Regular expression denial of service"},
        ],
        "jinja2": [
            {"below": "3.1.3", "cve": "CVE-2024-22195", "severity": "high",
             "title": "XSS via xmlattr filter"},
        ],
        "aiohttp": [
            {"below": "3.9.2", "cve": "CVE-2024-23334", "severity": "high",
             "title": "Directory traversal in static file serving"},
        ],
    }

    # License categories
    PERMISSIVE_LICENSES = {
        "MIT", "BSD", "Apache-2.0", "ISC", "BSD-2-Clause", "BSD-3-Clause",
        "Apache License 2.0", "MIT License", "BSD License",
        "Python Software Foundation License", "ZPL", "Zope Public License",
    }

    COPYLEFT_LICENSES = {
        "GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0",
        "GNU General Public License", "GPL", "AGPL",
    }

    def __init__(self, config=None):
        self.config = config
        self.name = "dependency_audit"

    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze dependencies for vulnerabilities and issues."""
        findings: List[Dict[str, Any]] = []
        suggestions: List[str] = []

        # ── Parse Dependency Files ────────────────────────────
        deps = self._parse_dependencies(code)
        dep_files = self._find_dependency_files(code)

        # ── Vulnerability Scanning ────────────────────────────
        vuln_findings = self._scan_vulnerabilities(deps)
        findings.extend(vuln_findings)

        # ── License Analysis ──────────────────────────────────
        license_findings = self._analyze_licenses(deps)
        findings.extend(license_findings)

        # ── Version Pinning Analysis ──────────────────────────
        pinning_findings = self._check_version_pinning(deps)
        findings.extend(pinning_findings)

        # ── Supply Chain Checks ───────────────────────────────
        supply_findings = self._check_supply_chain(code, deps)
        findings.extend(supply_findings)

        # ── Dev Dependencies Check ────────────────────────────
        dev_findings = self._check_dev_dependencies(code)
        findings.extend(dev_findings)

        # Generate suggestions
        if vuln_findings:
            suggestions.append("Update vulnerable packages immediately. Run 'pip-audit' or 'safety check' for full scan.")
        if license_findings:
            suggestions.append("Review copyleft licenses for compliance with your project's license.")
        if pinning_findings:
            suggestions.append("Pin dependency versions in production to avoid supply chain attacks.")
        if not findings:
            suggestions.append("No obvious dependency issues found. Run 'pip-audit' for a comprehensive CVE scan.")

        prompt_tokens = max(len(code) // 4, 500) + 1500
        completion_tokens = len(findings) * 150 + 1500

        return {
            "findings": findings,
            "vulnerabilities": vuln_findings,
            "metrics": {
                "total_dependencies": len(deps),
                "vulnerable_dependencies": len(vuln_findings),
                "license_issues": len(license_findings),
                "unpinned_dependencies": sum(1 for d in deps if d.get("version") == "latest"),
            },
            "suggestions": suggestions,
            "summary": (f"Audited {len(deps)} dependencies: "
                        f"{len(vuln_findings)} vulnerable, "
                        f"{len(license_findings)} license issues"),
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    # ── Dependency Parsing ─────────────────────────────────────

    def _parse_dependencies(self, code: str) -> List[Dict]:
        """Parse dependencies from various file formats."""
        deps = []

        # requirements.txt format
        for match in re.finditer(r'^([a-zA-Z0-9_-]+)\s*([><=!~]+\s*[\d.]+)?', code, re.MULTILINE):
            name = match.group(1).lower().strip()
            version = match.group(2).strip() if match.group(2) else "latest"
            if name and not name.startswith("#") and not name.startswith("-"):
                deps.append({"name": name, "version": version, "source": "requirements.txt"})

        # setup.py / setup.cfg
        for match in re.finditer(r'install_requires\s*=\s*\[(.*?)\]', code, re.DOTALL):
            for dep_match in re.finditer(r'["\']([a-zA-Z0-9_-]+)([><=!~]*[\d.]*)["\']', match.group(1)):
                deps.append({
                    "name": dep_match.group(1).lower(),
                    "version": dep_match.group(2) or "latest",
                    "source": "setup.py",
                })

        # pyproject.toml
        for match in re.finditer(r'dependencies\s*=\s*\[(.*?)\]', code, re.DOTALL):
            for dep_match in re.finditer(r'["\']([a-zA-Z0-9_-]+)([><=!~]*[\d.]*)["\']', match.group(1)):
                deps.append({
                    "name": dep_match.group(1).lower(),
                    "version": dep_match.group(2) or "latest",
                    "source": "pyproject.toml",
                })

        # Pipfile
        for match in re.finditer(r'^(\w+)\s*=\s*["\']([^"\']*)["\']', code, re.MULTILINE):
            name = match.group(1).lower()
            version = match.group(2)
            if name not in ("python_version", "name", "url", "verify_ssl"):
                deps.append({"name": name, "version": version, "source": "Pipfile"})

        # package.json
        for section in ["dependencies", "devDependencies"]:
            for match in re.finditer(rf'"{section}"\s*:\s*\{{(.*?)\}}', code, re.DOTALL):
                for dep_match in re.finditer(r'"([^"]+)"\s*:\s*"([^"]+)"', match.group(1)):
                    deps.append({
                        "name": dep_match.group(1).lower(),
                        "version": dep_match.group(2),
                        "source": f"package.json ({section})",
                        "is_dev": section == "devDependencies",
                    })

        return deps

    def _find_dependency_files(self, code: str) -> List[str]:
        """Identify which dependency files are present."""
        files = []
        patterns = [
            "requirements.txt", "setup.py", "setup.cfg", "pyproject.toml",
            "Pipfile", "Pipfile.lock", "package.json", "yarn.lock",
            "Gemfile", "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
        ]
        for p in patterns:
            if p.lower() in code.lower():
                files.append(p)
        return files

    # ── Vulnerability Scanning ─────────────────────────────────

    def _scan_vulnerabilities(self, deps: List[Dict]) -> List[Dict]:
        """Check dependencies against known vulnerability database."""
        findings = []

        for dep in deps:
            name = dep["name"].lower()
            version = dep["version"]

            if name in self.KNOWN_VULNERABILITIES:
                for vuln in self.KNOWN_VULNERABILITIES[name]:
                    # Simplified version comparison
                    if self._version_below(version, vuln["below"]):
                        findings.append({
                            "category": "Vulnerability",
                            "title": f"{name} {version}: {vuln['title']}",
                            "description": (f"Package '{name}' version {version} has known vulnerability "
                                           f"{vuln['cve']}. Update to >= {vuln['below']}."),
                            "severity": vuln["severity"],
                            "cwe_id": vuln["cve"],
                            "line_number": dep.get("line", 0),
                        })

        return findings

    def _version_below(self, current: str, target: str) -> bool:
        """Simplified version comparison."""
        if current == "latest" or not current:
            return False  # Can't determine, assume latest
        # Strip operators
        current = re.sub(r'^[><=!~]+', '', current).strip()
        target = target.strip()
        try:
            curr_parts = [int(x) for x in current.split(".")]
            tgt_parts = [int(x) for x in target.split(".")]
            # Pad to same length
            while len(curr_parts) < 3:
                curr_parts.append(0)
            while len(tgt_parts) < 3:
                tgt_parts.append(0)
            return curr_parts < tgt_parts
        except (ValueError, AttributeError):
            return False

    # ── License Analysis ───────────────────────────────────────

    def _analyze_licenses(self, deps: List[Dict]) -> List[Dict]:
        """Check for license compatibility issues."""
        findings = []
        # Note: In a real implementation, we'd query PyPI/npm for license info.
        # Here we check for common copyleft packages.
        known_copyleft = {
            "gpl", "agpl", "lgpl", "gcc", "gnuplot", "readline",
        }
        for dep in deps:
            if dep["name"] in known_copyleft:
                findings.append({
                    "category": "License",
                    "title": f"Copyleft license in '{dep['name']}'",
                    "description": (f"Package '{dep['name']}' may use a copyleft license (GPL/AGPL/LGPL). "
                                   f"Verify compatibility with your project's license."),
                    "severity": "medium",
                })
        return findings

    # ── Version Pinning ────────────────────────────────────────

    def _check_version_pinning(self, deps: List[Dict]) -> List[Dict]:
        """Check if dependencies have pinned versions."""
        findings = []
        unpinned = []
        for dep in deps:
            version = dep.get("version", "latest")
            if version in ("latest", "*", ""):
                unpinned.append(dep["name"])

        if unpinned:
            findings.append({
                "category": "Supply Chain",
                "title": f"{len(unpinned)} unpinned dependencies",
                "description": (f"Dependencies without pinned versions: {', '.join(unpinned[:10])}. "
                               f"Pin versions with == to prevent unexpected updates."),
                "severity": "medium",
            })

        # Check for overly permissive ranges
        for dep in deps:
            v = dep.get("version", "")
            if v.startswith(">=") and "<" not in v and "!=" not in v:
                findings.append({
                    "category": "Supply Chain",
                    "title": f"Unbounded version range for '{dep['name']}'",
                    "description": f"'{dep['name']} {v}' allows any future version. Add an upper bound.",
                    "severity": "low",
                })

        return findings

    # ── Supply Chain Checks ────────────────────────────────────

    def _check_supply_chain(self, code: str, deps: List[Dict]) -> List[Dict]:
        """Check for supply chain security indicators."""
        findings = []

        # Check for install scripts
        if re.search(r'install_requires.*setup\.py', code, re.DOTALL):
            if re.search(r'cmdclass|cmdclass\s*=|build_ext', code):
                findings.append({
                    "category": "Supply Chain",
                    "title": "Custom install script detected",
                    "description": "Package has custom install commands. Review for malicious code.",
                    "severity": "medium",
                })

        # Check for dependency confusion risks
        private_packages = set()
        for dep in deps:
            name = dep["name"]
            # Simple heuristic: packages with unusual names might be internal
            if re.match(r'^[a-z]+-[a-z]+-[a-z]+$', name) and name not in self.KNOWN_VULNERABILITIES:
                private_packages.add(name)

        if private_packages:
            findings.append({
                "category": "Supply Chain",
                "title": "Possible private packages in public registry",
                "description": (f"Packages that may be internal: {', '.join(list(private_packages)[:5])}. "
                               f"Use a private registry or --extra-index-url to prevent dependency confusion."),
                "severity": "medium",
            })

        return findings

    # ── Dev Dependencies Check ─────────────────────────────────

    def _check_dev_dependencies(self, code: str) -> List[Dict]:
        """Check for dev dependencies that shouldn't be in production."""
        findings = []
        dev_packages = {
            "pytest", "pytest-cov", "pytest-mock", "mock", "coverage",
            "tox", "flake8", "pylint", "mypy", "black", "isort", "autopep8",
            "debugpy", "ipython", "ipdb", "pdb",
        }

        # Check if dev packages are in main requirements
        for match in re.finditer(r'^([a-zA-Z0-9_-]+)', code, re.MULTILINE):
            name = match.group(1).lower().strip()
            if name in dev_packages:
                findings.append({
                    "category": "Dependencies",
                    "title": f"Dev dependency '{name}' in production requirements",
                    "description": f"'{name}' is a development tool. Move it to requirements-dev.txt or [dev] extras.",
                    "severity": "low",
                })

        return findings

    def estimate_tokens(self, code: str) -> int:
        code_tokens = max(len(code) // 4, 500)
        return code_tokens + 1500 + 3000
