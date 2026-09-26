from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    severity: str
    category: str
    pattern: re.Pattern[str] | None = None
    recommendation: str = ""


RULES = (
    Rule(
        "SEC001",
        "Possible SQL injection",
        "high",
        "security",
        re.compile(r"(?:execute|executemany)\s*\([^\n]*(?:f['\"]|%\s*\(|\.format\(|\+\s*)"),
        "Use parameterized queries instead of concatenating or interpolating user input.",
    ),
    Rule(
        "SEC002",
        "Hardcoded credential",
        "high",
        "security",
        re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|secret|token)\s*=\s*['\"][^'\"]+['\"]"),
        "Load secrets from environment variables or a secret manager.",
    ),
    Rule(
        "SEC003",
        "Dangerous dynamic execution",
        "high",
        "security",
        re.compile(r"\b(?:eval|exec)\s*\("),
        "Avoid dynamic execution of untrusted input; use a safe parser or an explicit allowlist.",
    ),
    Rule(
        "SEC004",
        "Weak cryptographic hash",
        "medium",
        "security",
        re.compile(r"\bhashlib\.(?:md5|sha1)\s*\("),
        "Use a modern hash such as SHA-256 or an appropriate password hashing algorithm.",
    ),
    Rule(
        "QUAL001",
        "Wildcard import",
        "low",
        "quality",
        re.compile(r"^\s*from\s+\S+\s+import\s+\*", re.MULTILINE),
        "Import only the names that are used to keep dependencies explicit.",
    ),
)


class SecurityQualityAgent:
    """Run a dependency-free first-pass security and quality review."""

    def review(self, code: str, language: str = "python") -> dict[str, object]:
        if not code.strip():
            raise ValueError("Code cannot be empty")

        findings: list[dict[str, object]] = []
        lines = code.splitlines()
        for rule in RULES:
            if rule.pattern is None:
                continue
            for match in rule.pattern.finditer(code):
                line_number = code.count("\n", 0, match.start()) + 1
                findings.append(self._finding(rule, line_number, lines[line_number - 1].strip()))

        if language.lower() in {"python", "py"}:
            findings.extend(self._review_python_ast(code, lines))

        findings.sort(key=lambda item: (item["line"], item["severity"], item["rule_id"]))
        counts = {severity: sum(item["severity"] == severity for item in findings) for severity in ("high", "medium", "low")}
        score = max(0, 100 - counts["high"] * 25 - counts["medium"] * 10 - counts["low"] * 3)
        return {
            "summary": {
                "risk_level": "high" if counts["high"] else "medium" if counts["medium"] else "low",
                "score": score,
                "finding_count": len(findings),
                "counts": counts,
            },
            "findings": findings,
            "agent": "security-quality",
            "language": language,
        }

    @staticmethod
    def _finding(rule: Rule, line: int, code: str) -> dict[str, object]:
        return {
            "rule_id": rule.rule_id,
            "title": rule.title,
            "severity": rule.severity,
            "category": rule.category,
            "line": line,
            "code": code,
            "recommendation": rule.recommendation,
        }

    @staticmethod
    def _review_python_ast(code: str, lines: list[str]) -> list[dict[str, object]]:
        try:
            tree = ast.parse(code)
        except SyntaxError as error:
            return [{
                "rule_id": "QUAL002",
                "title": "Syntax error prevents complete review",
                "severity": "medium",
                "category": "quality",
                "line": error.lineno or 1,
                "code": lines[(error.lineno or 1) - 1].strip() if lines else "",
                "recommendation": "Fix the syntax error before merging the code.",
            }]

        findings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append({
                    "rule_id": "QUAL003",
                    "title": "Bare exception handler",
                    "severity": "low",
                    "category": "quality",
                    "line": node.lineno,
                    "code": lines[node.lineno - 1].strip(),
                    "recommendation": "Catch the specific exceptions the code can handle.",
                })
        return findings


security_quality_agent = SecurityQualityAgent()