"""
SYNAPSE Security Scanner Agent
===============================
Detects security vulnerabilities by scanning code against OWASP Top 10
categories, injection vectors, XSS patterns, SSRF, authentication flaws,
hardcoded secrets, and insecure configurations.

Estimated token consumption: ~18,000 tokens per analysis
  - Prompt (system + code context): ~6,000 tokens
  - Analysis reasoning chain:       ~8,000 tokens
  - Findings & remediations:        ~4,000 tokens
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class SecurityScanner:
    """
    Security vulnerability detection agent.

    Scans source code for:
      - SQL Injection (CWE-89)
      - Cross-Site Scripting / XSS (CWE-79)
      - Command Injection (CWE-78)
      - Server-Side Request Forgery / SSRF (CWE-918)
      - Path Traversal (CWE-22)
      - Hardcoded Secrets & Credentials (CWE-798)
      - Insecure Deserialization (CWE-502)
      - Broken Authentication patterns (CWE-287)
      - Sensitive Data Exposure (CWE-200)
      - Security Misconfiguration (CWE-16)

    Token budget: ~18,000 tokens/analysis
    """

    ESTIMATED_TOKENS = 18_000

    # ── Pattern Definitions ────────────────────────────────────

    SQL_INJECTION_PATTERNS = [
        (r'(?:"|\')\s*(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\s+.*\+',
         "SQL query built via string concatenation",
         "CWE-89", "A03:2021-Injection"),
        (r'execute\s*\(\s*["\'].*%s',
         "SQL execute with %-formatting (possible injection)",
         "CWE-89", "A03:2021-Injection"),
        (r'cursor\.execute\s*\(\s*f["\']',
         "SQL execute with f-string interpolation",
         "CWE-89", "A03:2021-Injection"),
        (r'\.raw\s*\(\s*["\'].*(?:SELECT|INSERT|UPDATE|DELETE)',
         "ORM raw query - potential injection vector",
         "CWE-89", "A03:2021-Injection"),
        (r'(?:"|\')\s*OR\s+(?:"|\')\s*\d+\s*=\s*\d+',
         "Classic SQL injection tautology pattern",
         "CWE-89", "A03:2021-Injection"),
    ]

    XSS_PATTERNS = [
        (r'document\.write\s*\(',
         "document.write() - potential DOM XSS",
         "CWE-79", "A03:2021-Injection"),
        (r'innerHTML\s*=',
         "innerHTML assignment - potential XSS",
         "CWE-79", "A03:2021-Injection"),
        (r'\.html\s*\(\s*[^)]*\+',
         "jQuery .html() with concatenation - XSS risk",
         "CWE-79", "A03:2021-Injection"),
        (r'eval\s*\(\s*(?:request|params|input|user)',
         "eval() on user input - critical XSS/RCE",
         "CWE-79", "A03:2021-Injection"),
        (r'v-html\s*=',
         "Vue.js v-html directive - potential XSS",
         "CWE-79", "A03:2021-Injection"),
        (r'dangerouslySetInnerHTML',
         "React dangerouslySetInnerHTML - XSS risk",
         "CWE-79", "A03:2021-Injection"),
    ]

    COMMAND_INJECTION_PATTERNS = [
        (r'os\.system\s*\(',
         "os.system() call - command injection risk",
         "CWE-78", "A03:2021-Injection"),
        (r'subprocess\.(?:call|run|Popen)\s*\(.*shell\s*=\s*True',
         "subprocess with shell=True - command injection risk",
         "CWE-78", "A03:2021-Injection"),
        (r'exec\s*\(\s*(?:request|params|input)',
         "exec() on user input - RCE risk",
         "CWE-78", "A03:2021-Injection"),
        (r'child_process\.exec\s*\(',
         "Node.js child_process.exec - command injection risk",
         "CWE-78", "A03:2021-Injection"),
        (r'Runtime\.getRuntime\(\)\.exec',
         "Java Runtime.exec - command injection risk",
         "CWE-78", "A03:2021-Injection"),
    ]

    SSRF_PATTERNS = [
        (r'requests\.(?:get|post|put|delete|patch|head)\s*\(\s*(?:request|params|input|user)',
         "HTTP request to user-controlled URL - SSRF risk",
         "CWE-918", "A10:2021-SSRF"),
        (r'urllib\.request\.urlopen\s*\(\s*(?:request|params|input)',
         "urlopen with user input - SSRF risk",
         "CWE-918", "A10:2021-SSRF"),
        (r'fetch\s*\(\s*(?:req\.|request\.|params)',
         "fetch() with user-controlled URL - SSRF risk",
         "CWE-918", "A10:2021-SSRF"),
    ]

    PATH_TRAVERSAL_PATTERNS = [
        (r'open\s*\(\s*(?:request|params|input|user|filename)',
         "File open with user-controlled path - path traversal risk",
         "CWE-22", "A01:2021-Broken Access Control"),
        (r'send_file\s*\(\s*(?:request|params|input)',
         "send_file with user input - path traversal risk",
         "CWE-22", "A01:2021-Broken Access Control"),
        (r'(?:readFile|readFileSync)\s*\(\s*(?:req\.|request\.)',
         "Node.js readFile with user input - path traversal",
         "CWE-22", "A01:2021-Broken Access Control"),
    ]

    HARDCODED_SECRET_PATTERNS = [
        (r'(?i)(?:password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']',
         "Hardcoded password detected",
         "CWE-798", "A07:2021-Identification and Authentication Failures"),
        (r'(?i)(?:api[_-]?key|apikey)\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']',
         "Hardcoded API key detected",
         "CWE-798", "A07:2021-Identification and Authentication Failures"),
        (r'(?i)(?:secret[_-]?key|secret)\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']',
         "Hardcoded secret key detected",
         "CWE-798", "A07:2021-Identification and Authentication Failures"),
        (r'(?i)(?:aws[_-]?access[_-]?key[_-]?id|aws[_-]?secret)\s*=\s*["\']',
         "Hardcoded AWS credentials detected",
         "CWE-798", "A07:2021-Identification and Authentication Failures"),
        (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----',
         "Private key embedded in source code",
         "CWE-798", "A07:2021-Identification and Authentication Failures"),
    ]

    INSECURE_DESERIALIZATION_PATTERNS = [
        (r'pickle\.loads?\s*\(',
         "pickle deserialization - insecure deserialization risk",
         "CWE-502", "A08:2021-Software and Data Integrity Failures"),
        (r'yaml\.load\s*\([^)]*\)(?!.*Loader\s*=\s*SafeLoader)',
         "yaml.load without SafeLoader - code execution risk",
         "CWE-502", "A08:2021-Software and Data Integrity Failures"),
        (r'marshal\.loads?\s*\(',
         "marshal deserialization - insecure deserialization risk",
         "CWE-502", "A08:2021-Software and Data Integrity Failures"),
    ]

    AUTH_PATTERNS = [
        (r'(?i)if\s+(?:password|passwd)\s*==\s*["\']',
         "Plaintext password comparison - use constant-time comparison",
         "CWE-287", "A07:2021-Identification and Authentication Failures"),
        (r'(?i)verify\s*=\s*False',
         "SSL/TLS verification disabled",
         "CWE-295", "A07:2021-Identification and Authentication Failures"),
        (r'(?i)ALLOW_ALL_HOSTNAME_VERIFIER',
         "SSL hostname verification disabled",
         "CWE-295", "A07:2021-Identification and Authentication Failures"),
    ]

    WEAK_CRYPTO_PATTERNS = [
        (r'(?i)(?:md5|sha1)\s*\(',
         "Weak hash algorithm (MD5/SHA1) - use SHA-256+",
         "CWE-328", "A02:2021-Cryptographic Failures"),
        (r'DES\.|DESede\.',
         "Weak encryption algorithm (DES) - use AES-256",
         "CWE-327", "A02:2021-Cryptographic Failures"),
        (r'ECB\s*\(',
         "ECB mode encryption - use CBC or GCM",
         "CWE-327", "A02:2021-Cryptographic Failures"),
    ]

    # ── Initialization ─────────────────────────────────────────

    def __init__(self, config=None):
        self.config = config
        self.name = "security_scanner"

    # ── Analysis Entry Point ───────────────────────────────────

    async def analyze(self, code: str, context: dict) -> dict:
        """
        Scan the given source code for security vulnerabilities.

        Returns a dict with keys:
            findings, vulnerabilities, metrics, suggestions, summary, token_usage
        """
        findings: List[Dict[str, Any]] = []
        vulns: List[Dict[str, Any]] = []
        suggestions: List[str] = []

        # Category -> list of (pattern, description, cwe, owasp)
        categories = [
            ("SQL Injection",          self.SQL_INJECTION_PATTERNS,          "high"),
            ("Cross-Site Scripting",   self.XSS_PATTERNS,                   "high"),
            ("Command Injection",      self.COMMAND_INJECTION_PATTERNS,      "critical"),
            ("SSRF",                   self.SSRF_PATTERNS,                   "high"),
            ("Path Traversal",         self.PATH_TRAVERSAL_PATTERNS,         "high"),
            ("Hardcoded Secrets",      self.HARDCODED_SECRET_PATTERNS,       "critical"),
            ("Insecure Deserialization", self.INSECURE_DESERIALIZATION_PATTERNS, "high"),
            ("Authentication Issues",  self.AUTH_PATTERNS,                   "high"),
            ("Weak Cryptography",      self.WEAK_CRYPTO_PATTERNS,            "medium"),
        ]

        lines = code.split("\n")

        for category_name, patterns, default_severity in categories:
            for pattern_str, description, cwe_id, owasp in patterns:
                for line_num, line in enumerate(lines, 1):
                    if re.search(pattern_str, line):
                        finding = {
                            "category": category_name,
                            "title": description,
                            "severity": default_severity,
                            "line_number": line_num,
                            "code_snippet": line.strip()[:200],
                            "cwe_id": cwe_id,
                            "owasp_category": owasp,
                            "confidence": self._estimate_confidence(line, pattern_str),
                        }
                        findings.append(finding)
                        vulns.append(finding)

        # Generate remediation suggestions
        seen_categories = set()
        for f in findings:
            cat = f["category"]
            if cat not in seen_categories:
                seen_categories.add(cat)
                suggestions.append(self._get_remediation(cat))

        # Additional heuristic checks
        suggestions.extend(self._heuristic_checks(code, lines))

        prompt_tokens = self._estimate_prompt_tokens(code)
        completion_tokens = self._estimate_completion_tokens(findings)

        summary_parts = [f"Found {len(findings)} security issue(s)"]
        sev_counts = {}
        for f in findings:
            sev = f["severity"]
            sev_counts[sev] = sev_counts.get(sev, 0) + 1
        for sev in ["critical", "high", "medium", "low"]:
            if sev in sev_counts:
                summary_parts.append(f"  {sev_counts[sev]} {sev}")

        return {
            "findings": findings,
            "vulnerabilities": vulns,
            "metrics": {},
            "suggestions": suggestions,
            "summary": "; ".join(summary_parts),
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    # ── Helpers ────────────────────────────────────────────────

    def _estimate_confidence(self, line: str, pattern: str) -> float:
        """Heuristic confidence score based on context around the match."""
        stripped = line.strip()
        # Comments lower confidence
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
            return 0.3
        # Test files lower confidence
        if "test" in stripped.lower() or "mock" in stripped.lower():
            return 0.4
        # String with concatenation is higher confidence
        if "+" in stripped or "f'" in stripped or 'f"' in stripped:
            return 0.9
        return 0.75

    def _get_remediation(self, category: str) -> str:
        """Return a remediation suggestion for a vulnerability category."""
        remediations = {
            "SQL Injection": "Use parameterized queries or ORM methods. Never concatenate user input into SQL strings.",
            "Cross-Site Scripting": "Sanitize and escape all user input before rendering. Use templating engines with auto-escaping.",
            "Command Injection": "Avoid shell execution with user input. Use subprocess with argument lists, never shell=True.",
            "SSRF": "Validate and whitelist allowed URLs/domains. Use allow-lists for outbound requests.",
            "Path Traversal": "Validate file paths against a whitelist. Use os.path.realpath() and verify the resolved path is within allowed directories.",
            "Hardcoded Secrets": "Move secrets to environment variables or a secret manager (e.g., AWS Secrets Manager, HashiCorp Vault).",
            "Insecure Deserialization": "Avoid deserializing untrusted data. Use safe loaders (yaml.safe_load) and validate data after deserialization.",
            "Authentication Issues": "Use bcrypt/argon2 for password hashing. Never compare passwords in plaintext. Enable SSL verification.",
            "Weak Cryptography": "Use modern algorithms: SHA-256+ for hashing, AES-256-GCM for encryption. Avoid MD5, SHA1, DES, ECB.",
        }
        return remediations.get(category, "Review and remediate the identified security issue.")

    def _heuristic_checks(self, code: str, lines: List[str]) -> List[str]:
        """Additional heuristic security checks beyond regex patterns."""
        extras = []
        # Check for debug mode in production code
        if re.search(r'(?i)DEBUG\s*=\s*True', code):
            extras.append("Ensure DEBUG=False in production deployments.")
        # Check for CORS wildcard
        if re.search(r'(?i)(?:cors|CORS).*(?:\*|allow.?all)', code):
            extras.append("Avoid CORS wildcard (*) in production. Restrict to specific origins.")
        # Check for missing CSRF protection
        if re.search(r'(?i)csrf_exempt', code):
            extras.append("CSRF exemption detected. Ensure this is intentional and limited.")
        return extras

    def _estimate_prompt_tokens(self, code: str) -> int:
        """Estimate prompt tokens: system prompt + code context."""
        # Rough estimate: 1 token per 4 characters of code, plus ~2000 for system prompt
        code_tokens = max(len(code) // 4, 500)
        system_overhead = 2000
        return code_tokens + system_overhead

    def _estimate_completion_tokens(self, findings: List[dict]) -> int:
        """Estimate completion tokens based on number of findings."""
        # ~200 tokens per finding description + 1000 base analysis
        return len(findings) * 200 + 1000

    def estimate_tokens(self, code: str) -> int:
        """Public method to estimate total token consumption for this agent."""
        prompt = self._estimate_prompt_tokens(code)
        # Assume average 5 findings
        completion = 5 * 200 + 1000
        return prompt + completion
