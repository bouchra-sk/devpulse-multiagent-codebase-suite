"""
Tests pour l'Agent 5 : IBM Bob Refactoring Agent.

Utilise unittest.mock.patch pour simuler call_llm :
  - ne dépend PAS d'une vraie clé IBM Bob 2.0 ;
  - teste le fallback déterministe (_auto_fix_all) pour les 4 règles :
      SEC001 : SQL injection (concaténation → requête paramétrée + execute)
      SEC002 : Credential hardcodé (→ os.getenv)
      SEC003 : eval() dangereux (→ int() avec ValueError pour les IDs numériques)
      QUAL002 : Erreur de syntaxe (→ mot-clé `def` restauré)
  - teste le chemin LLM réel (réponse JSON valide) ;
  - vérifie la syntaxe du code retourné ;
  - vérifie la régression : l'output repassé dans l'Agent 4 ne doit plus
    déclencher les mêmes findings.
"""

import ast
import json
import pytest
from unittest.mock import patch

from backend.Agent5.refactoring_agent import (
    refactor_code,
    _auto_fix_all,
    _format_findings,
    _parse_json_response,
)
from backend.Agent4.security_quality_agent import SecurityQualityAgent


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures locales (complètent celles de conftest.py)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def agent4() -> SecurityQualityAgent:
    return SecurityQualityAgent()


@pytest.fixture
def sec001_finding() -> dict:
    """Finding SEC001 sur 'query = "SELECT..." + user_id' à la ligne 3."""
    return {
        "rule_id": "SEC001",
        "title": "Possible SQL injection",
        "severity": "high",
        "category": "security",
        "line": 3,
        "code": '"SELECT * FROM users WHERE id = " + user_id',
        "recommendation": "Use parameterized queries.",
    }


@pytest.fixture
def qual002_finding() -> dict:
    """Finding QUAL002 sur 'ef broken_func():' à la ligne 1."""
    return {
        "rule_id": "QUAL002",
        "title": "Syntax error prevents complete review",
        "severity": "medium",
        "category": "quality",
        "line": 1,
        "code": "ef broken_func():",
        "recommendation": "Fix the syntax error before merging the code.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# _auto_fix_all — SEC002 : hardcoded credential
# ─────────────────────────────────────────────────────────────────────────────

def test_sec002_replaces_hardcoded_password(sec002_finding, vulnerable_code):
    """Le correctif SEC002 doit remplacer la valeur littérale par os.getenv()."""
    result = _auto_fix_all(vulnerable_code, [sec002_finding])
    assert 'os.getenv("PASSWORD")' in result["fixed_code"]
    assert '"admin123"' not in result["fixed_code"]
    assert any("SEC002" in a or "PASSWORD" in a for a in result["applied"])


def test_sec002_adds_import_os():
    code = 'password = "admin123"\n'
    finding = {
        "rule_id": "SEC002",
        "line": 1,
        "code": 'password = "admin123"',
        "title": "Hardcoded credential",
        "severity": "high",
        "category": "security",
        "recommendation": "Use env var.",
    }
    result = _auto_fix_all(code, [finding])
    assert "import os" in result["fixed_code"]


def test_sec002_does_not_duplicate_import_os():
    code = 'import os\npassword = "secret"\n'
    finding = {
        "rule_id": "SEC002", "line": 2,
        "code": 'password = "secret"', "title": "HC", "severity": "high",
        "category": "security", "recommendation": "Use env var.",
    }
    result = _auto_fix_all(code, [finding])
    assert result["fixed_code"].count("import os") == 1


def test_sec002_no_original_secret_in_output(sec002_finding, vulnerable_code):
    result = _auto_fix_all(vulnerable_code, [sec002_finding])
    assert "admin123" not in result["fixed_code"]


# ─────────────────────────────────────────────────────────────────────────────
# _auto_fix_all — SEC001 : SQL injection
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sql_injection_code() -> str:
    return (
        "def get_user(user_id):\n"
        "    conn = get_connection()\n"
        '    query = "SELECT * FROM users WHERE id = " + user_id\n'
        "    return query\n"
    )


@pytest.fixture
def sql_injection_finding() -> dict:
    return {
        "rule_id": "SEC001",
        "title": "Possible SQL injection",
        "severity": "high",
        "category": "security",
        "line": 3,
        "code": '"SELECT * FROM users WHERE id = " + user_id',
        "recommendation": "Use parameterized queries.",
    }


def test_sec001_replaces_concatenation_with_placeholder(
    sql_injection_code, sql_injection_finding
):
    """Le correctif SEC001 doit remplacer + user_id par un placeholder ?."""
    result = _auto_fix_all(sql_injection_code, [sql_injection_finding])
    fixed = result["fixed_code"]
    assert "?" in fixed
    assert '+ user_id' not in fixed
    assert "SEC001" in result["applied"][0] or "query" in result["applied"][0]


def test_sec001_creates_params_tuple(sql_injection_code, sql_injection_finding):
    """Le correctif SEC001 doit créer une variable query_params."""
    result = _auto_fix_all(sql_injection_code, [sql_injection_finding])
    assert "query_params" in result["fixed_code"]
    assert "user_id" in result["fixed_code"]  # la valeur est préservée dans le tuple


def test_sec001_adds_cursor_execute_call(sql_injection_code, sql_injection_finding):
    """
    Le correctif SEC001 doit ajouter cursor.execute(query, query_params).
    Sans cet appel, les paramètres seraient créés mais jamais utilisés.
    """
    result = _auto_fix_all(sql_injection_code, [sql_injection_finding])
    fixed = result["fixed_code"]
    assert "cursor.execute(query, query_params)" in fixed, (
        f"cursor.execute(query, query_params) absent du code corrigé :\n{fixed}"
    )


def test_sec001_fixed_code_is_syntactically_valid(sql_injection_code, sql_injection_finding):
    result = _auto_fix_all(sql_injection_code, [sql_injection_finding])
    try:
        ast.parse(result["fixed_code"])
    except SyntaxError as exc:
        pytest.fail(f"Code SEC001 corrigé invalide syntaxiquement : {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# _auto_fix_all — SEC003 : eval() dangereux
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def eval_user_id_code() -> str:
    return (
        "def get_user(user_id):\n"
        "    result = eval(user_id)\n"
        "    return result\n"
    )


@pytest.fixture
def eval_user_id_finding() -> dict:
    return {
        "rule_id": "SEC003",
        "title": "Dangerous dynamic execution",
        "severity": "high",
        "category": "security",
        "line": 2,
        "code": "result = eval(user_id)",
        "recommendation": "Use int() or ast.literal_eval().",
    }


def test_sec003_removes_eval_call(eval_user_id_code, eval_user_id_finding):
    """Le correctif SEC003 ne doit JAMAIS laisser un appel eval() nu dans le code."""
    import re as _re
    result = _auto_fix_all(eval_user_id_code, [eval_user_id_finding])
    fixed = result["fixed_code"]
    bare_eval = _re.search(r'(?<!literal_)eval\(', fixed)
    assert bare_eval is None, (
        f"eval() nu encore présent dans le code corrigé :\n{fixed}"
    )


def test_sec003_user_id_uses_int_not_ast_literal_eval(eval_user_id_code, eval_user_id_finding):
    """
    Pour user_id (identifiant numérique), le correctif doit utiliser int(),
    pas ast.literal_eval(). Utiliser ast.literal_eval() pour un ID numérique
    est incorrect : int("5") == 5 mais ast.literal_eval("5") == 5 aussi —
    cependant l'intent sémantique est différent et int() lève ValueError pour
    une valeur non numérique, ce qui est le comportement souhaité pour un ID.
    """
    result = _auto_fix_all(eval_user_id_code, [eval_user_id_finding])
    fixed = result["fixed_code"]
    assert "int(user_id)" in fixed, (
        f"int(user_id) attendu pour un ID numérique, code corrigé :\n{fixed}"
    )
    assert "ast.literal_eval(user_id)" not in fixed, (
        f"ast.literal_eval() ne doit pas être utilisé pour un ID numérique, "
        f"code corrigé :\n{fixed}"
    )


def test_sec003_user_id_has_valueerror_handling(eval_user_id_code, eval_user_id_finding):
    """Le correctif doit inclure try/except ValueError pour int()."""
    result = _auto_fix_all(eval_user_id_code, [eval_user_id_finding])
    fixed = result["fixed_code"]
    assert "ValueError" in fixed, (
        f"try/except ValueError absent du code corrigé :\n{fixed}"
    )
    assert "try:" in fixed


def test_sec003_fixed_code_is_syntactically_valid(eval_user_id_code, eval_user_id_finding):
    result = _auto_fix_all(eval_user_id_code, [eval_user_id_finding])
    try:
        ast.parse(result["fixed_code"])
    except SyntaxError as exc:
        pytest.fail(f"Code SEC003 corrigé invalide syntaxiquement : {exc}")


def test_sec003_non_id_uses_ast_literal_eval():
    """Pour une expression non-numérique (ex: data), ast.literal_eval() est correct."""
    code = "parsed = eval(data)\n"
    finding = {
        "rule_id": "SEC003",
        "title": "Dangerous dynamic execution",
        "severity": "high",
        "category": "security",
        "line": 1,
        "code": "parsed = eval(data)",
        "recommendation": "Use ast.literal_eval().",
    }
    result = _auto_fix_all(code, [finding])
    fixed = result["fixed_code"]
    assert "ast.literal_eval(data)" in fixed
    # "eval(" est sous-chaîne de "literal_eval(" — on vérifie l'absence du
    # mot-clé nu `eval(` en s'assurant qu'il n'est PAS précédé par "literal_".
    import re as _re
    bare_eval = _re.search(r'(?<!literal_)eval\(', fixed)
    assert bare_eval is None, (
        f"eval() nu encore présent dans le code corrigé :\n{fixed}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# _auto_fix_all — QUAL002 : erreur de syntaxe (def tronqué en ef)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def syntax_error_code() -> str:
    return "ef broken_func():\n    return 42\n"


@pytest.fixture
def qual002_finding_line1() -> dict:
    return {
        "rule_id": "QUAL002",
        "title": "Syntax error prevents complete review",
        "severity": "medium",
        "category": "quality",
        "line": 1,
        "code": "ef broken_func():",
        "recommendation": "Fix the syntax error before merging the code.",
    }


def test_qual002_restores_def_keyword(syntax_error_code, qual002_finding_line1):
    """QUAL002 doit restaurer `def` à partir de `ef`."""
    result = _auto_fix_all(syntax_error_code, [qual002_finding_line1])
    assert result["fixed_code"].startswith("def broken_func():")


def test_qual002_fixed_code_is_syntactically_valid(syntax_error_code, qual002_finding_line1):
    """Le code corrigé doit être parsable par ast.parse()."""
    result = _auto_fix_all(syntax_error_code, [qual002_finding_line1])
    try:
        ast.parse(result["fixed_code"])
    except SyntaxError as exc:
        pytest.fail(f"Code QUAL002 corrigé invalide syntaxiquement : {exc}")


def test_qual002_removes_syntax_error(syntax_error_code, qual002_finding_line1):
    """Après correction, Agent 4 ne doit plus signaler de QUAL002."""
    result = _auto_fix_all(syntax_error_code, [qual002_finding_line1])
    report = SecurityQualityAgent().review(result["fixed_code"])
    qual002s = [f for f in report["findings"] if f["rule_id"] == "QUAL002"]
    assert qual002s == [], f"QUAL002 encore présent après correction : {qual002s}"


# ─────────────────────────────────────────────────────────────────────────────
# _auto_fix_all — combinaison de plusieurs règles en même temps
# ─────────────────────────────────────────────────────────────────────────────

VULNERABLE_FULL = (
    "def get_user(user_id):\n"
    '    password = "admin123"\n'
    '    query = "SELECT * FROM users WHERE id = " + user_id\n'
    "    result = eval(user_id)\n"
    "    return query, password, result\n"
)


def _all_findings_for_vulnerable_full() -> list[dict]:
    return [
        {
            "rule_id": "SEC002",
            "title": "Hardcoded credential",
            "severity": "high",
            "category": "security",
            "line": 2,
            "code": 'password = "admin123"',
            "recommendation": "Use env var.",
        },
        {
            "rule_id": "SEC001",
            "title": "Possible SQL injection",
            "severity": "high",
            "category": "security",
            "line": 3,
            "code": '"SELECT * FROM users WHERE id = " + user_id',
            "recommendation": "Use parameterized queries.",
        },
        {
            "rule_id": "SEC003",
            "title": "Dangerous dynamic execution",
            "severity": "high",
            "category": "security",
            "line": 4,
            "code": "result = eval(user_id)",
            "recommendation": "Use int() or ast.literal_eval().",
        },
    ]


def test_multi_rule_fix_applies_all_three():
    import re as _re
    findings = _all_findings_for_vulnerable_full()
    result = _auto_fix_all(VULNERABLE_FULL, findings)
    fixed = result["fixed_code"]

    # SEC002 : pas de valeur littérale
    assert '"admin123"' not in fixed
    assert 'os.getenv("PASSWORD")' in fixed

    # SEC001 : pas de concaténation, query_params présent, cursor.execute présent
    assert '+ user_id' not in fixed
    assert "query_params" in fixed
    assert "cursor.execute(query, query_params)" in fixed

    # SEC003 : pas d'eval nu, int(user_id) présent
    bare_eval = _re.search(r'(?<!literal_)eval\(', fixed)
    assert bare_eval is None, f"eval() nu encore présent : {fixed}"
    assert "int(user_id)" in fixed


def test_multi_rule_fix_output_is_syntactically_valid():
    findings = _all_findings_for_vulnerable_full()
    result = _auto_fix_all(VULNERABLE_FULL, findings)
    try:
        ast.parse(result["fixed_code"])
    except SyntaxError as exc:
        pytest.fail(f"Code multi-règles corrigé invalide syntaxiquement : {exc}")


def test_multi_rule_fix_no_remaining_rule_ids():
    findings = _all_findings_for_vulnerable_full()
    result = _auto_fix_all(VULNERABLE_FULL, findings)
    assert result["remaining_rule_ids"] == [], (
        f"Des règles n'ont pas pu être corrigées automatiquement : "
        f"{result['remaining_rule_ids']}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Régression : output de l'Agent 5 repassé dans l'Agent 4
# ─────────────────────────────────────────────────────────────────────────────

def test_regression_refactored_output_clears_sec002_and_sec003(agent4):
    """
    Après correction par l'Agent 5, l'Agent 4 ne doit plus détecter
    SEC002 (password hardcodé) ni SEC003 (eval) dans le code corrigé.
    """
    findings = _all_findings_for_vulnerable_full()
    fix_result = _auto_fix_all(VULNERABLE_FULL, findings)
    fixed_code = fix_result["fixed_code"]

    report = agent4.review(fixed_code)
    rule_ids = {f["rule_id"] for f in report["findings"]}

    assert "SEC002" not in rule_ids, (
        f"SEC002 encore détecté après correction : "
        f"{[f for f in report['findings'] if f['rule_id'] == 'SEC002']}"
    )
    assert "SEC003" not in rule_ids, (
        f"SEC003 encore détecté après correction : "
        f"{[f for f in report['findings'] if f['rule_id'] == 'SEC003']}"
    )


def test_regression_refactored_output_clears_sec001(agent4):
    """
    Après correction SEC001, l'Agent 4 ne doit plus détecter d'injection SQL
    via la concaténation directe dans le code corrigé.
    """
    code = (
        "def get_user(user_id):\n"
        '    query = "SELECT * FROM users WHERE id = " + user_id\n'
        "    return query\n"
    )
    finding = {
        "rule_id": "SEC001",
        "line": 2,
        "code": '"SELECT * FROM users WHERE id = " + user_id',
        "title": "SQL injection",
        "severity": "high",
        "category": "security",
        "recommendation": "Use parameterized queries.",
    }
    fix_result = _auto_fix_all(code, [finding])
    report = agent4.review(fix_result["fixed_code"])
    sec001s = [f for f in report["findings"] if f["rule_id"] == "SEC001"]
    assert sec001s == [], (
        f"SEC001 encore détecté après correction :\n"
        f"Code corrigé :\n{fix_result['fixed_code']}\n"
        f"Findings restants : {sec001s}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# _format_findings
# ─────────────────────────────────────────────────────────────────────────────

def test_format_findings_empty():
    result = _format_findings([])
    assert result == "Aucun problème détecté par l'Agent 4."


def test_format_findings_includes_rule_id_and_line(sec002_finding):
    result = _format_findings([sec002_finding])
    assert "SEC002" in result
    assert "2" in result  # numéro de ligne


def test_format_findings_includes_code_snippet(sec002_finding):
    result = _format_findings([sec002_finding])
    assert "admin123" in result or "password" in result.lower()


# ─────────────────────────────────────────────────────────────────────────────
# _parse_json_response
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_json_response_valid():
    raw = json.dumps({
        "refactored_code": "def foo(): pass",
        "changes_summary": "Fixed issues.",
    })
    result = _parse_json_response(raw)
    assert result["refactored_code"] == "def foo(): pass"
    assert result["changes_summary"] == "Fixed issues."


def test_parse_json_response_strips_markdown_fences():
    raw = "```json\n" + json.dumps({"refactored_code": "x = 1"}) + "\n```"
    result = _parse_json_response(raw)
    assert result["refactored_code"] == "x = 1"


def test_parse_json_response_raises_on_invalid_json():
    with pytest.raises(RuntimeError, match="non parsable"):
        _parse_json_response("not a json string")


def test_parse_json_response_raises_on_missing_key():
    raw = json.dumps({"changes_summary": "summary only"})
    with pytest.raises(RuntimeError, match="refactored_code"):
        _parse_json_response(raw)


# ─────────────────────────────────────────────────────────────────────────────
# refactor_code — chemin mock (LLM indisponible)
# ─────────────────────────────────────────────────────────────────────────────

def test_refactor_code_mock_applies_sec002_fix(vulnerable_code, sec002_finding, sec003_finding):
    """En mode mock, Agent 5 doit appliquer le correctif SEC002."""
    with patch("backend.Agent5.refactoring_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "", "mocked": True}
        result = refactor_code(vulnerable_code, [sec002_finding, sec003_finding])

    assert result["mocked"] is True
    assert 'os.getenv("PASSWORD")' in result["refactored_code"]
    assert '"admin123"' not in result["refactored_code"]


def test_refactor_code_mock_applies_sec003_fix_with_int(vulnerable_code, sec003_finding):
    """En mode mock, Agent 5 doit remplacer eval(user_id) par int(user_id)."""
    import re as _re
    with patch("backend.Agent5.refactoring_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "", "mocked": True}
        result = refactor_code(vulnerable_code, [sec003_finding])

    fixed = result["refactored_code"]
    bare_eval = _re.search(r'(?<!literal_)eval\(', fixed)
    assert bare_eval is None, f"eval() nu encore présent : {fixed}"
    assert "int(user_id)" in fixed
    assert "ValueError" in fixed


def test_refactor_code_mock_returns_valid_syntax(vulnerable_code, sec002_finding, sec003_finding):
    with patch("backend.Agent5.refactoring_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "", "mocked": True}
        result = refactor_code(vulnerable_code, [sec002_finding, sec003_finding])

    try:
        ast.parse(result["refactored_code"])
    except SyntaxError as exc:
        pytest.fail(f"Le code refactorisé a une erreur de syntaxe : {exc}")


def test_refactor_code_mock_no_findings_returns_unchanged(vulnerable_code):
    with patch("backend.Agent5.refactoring_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "", "mocked": True}
        result = refactor_code(vulnerable_code, [])

    assert "Aucun problème" in result["changes_summary"]


# ─────────────────────────────────────────────────────────────────────────────
# refactor_code — chemin LLM réel (réponse mockée valide)
# ─────────────────────────────────────────────────────────────────────────────

SECURE_CODE = (
    "import os\n\n"
    "def get_user(user_id: int):\n"
    '    password = os.getenv("PASSWORD")\n'
    '    query = "SELECT * FROM users WHERE id = ?"\n'
    "    query_params = (user_id,)\n"
    "    cursor.execute(query, query_params)\n"
    "    try:\n"
    "        uid = int(user_id)\n"
    "    except ValueError as exc:\n"
    '        raise ValueError(f"Invalid numeric ID: {user_id!r}") from exc\n'
    "    return query, password\n"
)


def test_refactor_code_real_llm_path_parses_json(vulnerable_code, sec002_finding):
    fake_response = json.dumps({
        "refactored_code": SECURE_CODE,
        "changes_summary": "Replaced hardcoded credential and removed eval().",
    })
    with patch("backend.Agent5.refactoring_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": fake_response, "mocked": False}
        result = refactor_code(vulnerable_code, [sec002_finding])

    assert result["mocked"] is False
    assert result["refactored_code"] == SECURE_CODE
    assert "Replaced" in result["changes_summary"]


def test_refactor_code_real_llm_invalid_json_raises(vulnerable_code, sec002_finding):
    with patch("backend.Agent5.refactoring_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "not a json", "mocked": False}
        with pytest.raises(RuntimeError, match="non parsable"):
            refactor_code(vulnerable_code, [sec002_finding])


def test_refactor_code_real_llm_missing_key_raises(vulnerable_code, sec002_finding):
    bad_response = json.dumps({"changes_summary": "summary only"})
    with patch("backend.Agent5.refactoring_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": bad_response, "mocked": False}
        with pytest.raises(RuntimeError, match="refactored_code"):
            refactor_code(vulnerable_code, [sec002_finding])
