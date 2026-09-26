"""
Tests pour l'Agent 6 : Automated Test Generator & Validator Agent.

Couvre :
  - _check_syntax         : détection d'erreurs de syntaxe
  - _count_test_functions : comptage des fonctions test_*
  - _run_pytest           : exécution réelle de pytest
  - _generate_fallback_tests : génération de tests sans LLM (retourne dict)
  - _parse_llm_response   : parsing et validation de la réponse JSON du LLM
  - generate_tests        : chemin mock + chemin LLM réel (avec mocks)
                            + propagation des erreurs API

Tests IBM Bob réels (vraie clé) : NON inclus ici — ils nécessitent
LLM_API_URL + LLM_API_KEY configurés et sont à lancer séparément.
"""

import ast
import json
import pytest
from unittest.mock import patch

from backend.Agent6.test_generator_agent import (
    generate_tests,
    _check_syntax,
    _count_test_functions,
    _run_pytest,
    _generate_fallback_tests,
    _parse_llm_response,
)


# ─────────────────────────────────────────────────────────────────────────────
# _check_syntax
# ─────────────────────────────────────────────────────────────────────────────

def test_check_syntax_valid_code():
    errors = _check_syntax("def foo():\n    return 1\n")
    assert errors == []


def test_check_syntax_invalid_code():
    errors = _check_syntax("def foo(\n    pass\n")
    assert len(errors) == 1
    assert "syntaxe" in errors[0].lower() or "syntax" in errors[0].lower()


def test_check_syntax_empty_string():
    errors = _check_syntax("")
    assert errors == []


def test_check_syntax_includes_line_number():
    errors = _check_syntax("def foo(\n    pass\n")
    assert "1" in errors[0] or "2" in errors[0]  # numéro de ligne présent


# ─────────────────────────────────────────────────────────────────────────────
# _count_test_functions
# ─────────────────────────────────────────────────────────────────────────────

def test_count_test_functions_zero():
    code = "def helper():\n    pass\n"
    assert _count_test_functions(code) == 0


def test_count_test_functions_one():
    code = "def test_foo():\n    assert True\n"
    assert _count_test_functions(code) == 1


def test_count_test_functions_multiple():
    code = (
        "def test_a():\n    pass\n"
        "def test_b():\n    pass\n"
        "def helper():\n    pass\n"
    )
    assert _count_test_functions(code) == 2


def test_count_test_functions_syntax_error_returns_zero():
    assert _count_test_functions("def bad(:\n    pass\n") == 0


# ─────────────────────────────────────────────────────────────────────────────
# _generate_fallback_tests — retourne maintenant un dict
# ─────────────────────────────────────────────────────────────────────────────

def test_fallback_returns_dict(vulnerable_code):
    result = _generate_fallback_tests(vulnerable_code)
    assert isinstance(result, dict)
    assert "filename" in result
    assert "test_code" in result
    assert "test_count" in result
    assert "explanation" in result


def test_fallback_filename_is_simulation(vulnerable_code):
    result = _generate_fallback_tests(vulnerable_code)
    assert "simulation" in result["filename"]


def test_fallback_test_code_is_syntactically_valid(vulnerable_code):
    result = _generate_fallback_tests(vulnerable_code)
    try:
        ast.parse(result["test_code"])
    except SyntaxError as exc:
        pytest.fail(f"Syntaxe invalide dans les tests de fallback : {exc}")


def test_fallback_test_code_contains_test_function(vulnerable_code):
    result = _generate_fallback_tests(vulnerable_code)
    assert "def test_" in result["test_code"]


def test_fallback_test_code_includes_syntax_check(vulnerable_code):
    result = _generate_fallback_tests(vulnerable_code)
    assert "test_refactored_code_is_syntactically_valid" in result["test_code"]


def test_fallback_test_code_includes_no_bare_eval_check(vulnerable_code):
    result = _generate_fallback_tests(vulnerable_code)
    assert "test_refactored_code_has_no_bare_eval" in result["test_code"]


def test_fallback_test_count_matches_actual(vulnerable_code):
    result = _generate_fallback_tests(vulnerable_code)
    actual = _count_test_functions(result["test_code"])
    assert result["test_count"] == actual


def test_fallback_detects_function_names():
    code = "def my_func():\n    return 42\n"
    result = _generate_fallback_tests(code)
    assert "my_func" in result["test_code"]


def test_fallback_detects_os_getenv():
    code = (
        "import os\n"
        "def get_password():\n"
        '    return os.getenv("PASSWORD")\n'
    )
    result = _generate_fallback_tests(code)
    assert "os.getenv" in result["test_code"]
    assert "os.getenv()" in result["explanation"]


def test_fallback_detects_cursor_execute():
    code = (
        'query = "SELECT * FROM t WHERE id = ?"\n'
        "query_params = (user_id,)\n"
        "cursor.execute(query, query_params)\n"
    )
    result = _generate_fallback_tests(code)
    assert "cursor.execute" in result["test_code"]
    assert "cursor.execute()" in result["explanation"]


def test_fallback_explanation_mentions_simulation(vulnerable_code):
    result = _generate_fallback_tests(vulnerable_code)
    assert "simulation" in result["explanation"].lower()


def test_fallback_with_invalid_syntax_still_produces_test():
    """Même sur du code syntaxiquement invalide, le fallback doit produire un test."""
    bad_code = "def bad(:\n    pass\n"
    result = _generate_fallback_tests(bad_code)
    try:
        ast.parse(result["test_code"])
    except SyntaxError as exc:
        pytest.fail(f"Le fallback lui-même a une erreur de syntaxe : {exc}")
    assert result["test_count"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# _parse_llm_response
# ─────────────────────────────────────────────────────────────────────────────

MINIMAL_TEST = "def test_x():\n    assert True\n"


def test_parse_llm_response_full_valid():
    raw = json.dumps({
        "filename": "test_generated.py",
        "test_code": MINIMAL_TEST,
        "test_count": 1,
        "explanation": "Tests couvrent la fonction principale.",
    })
    result = _parse_llm_response(raw)
    assert result["filename"] == "test_generated.py"
    assert result["test_code"] == MINIMAL_TEST
    assert result["test_count"] == 1
    assert "principale" in result["explanation"]


def test_parse_llm_response_defaults_filename():
    raw = json.dumps({"test_code": MINIMAL_TEST})
    result = _parse_llm_response(raw)
    assert result["filename"] == "test_generated.py"


def test_parse_llm_response_recalculates_test_count_if_wrong():
    raw = json.dumps({
        "test_code": MINIMAL_TEST,
        "test_count": 999,  # valeur intentionnellement fausse
    })
    result = _parse_llm_response(raw)
    assert result["test_count"] == 1  # recalculé depuis le code


def test_parse_llm_response_recalculates_test_count_if_missing():
    raw = json.dumps({"test_code": MINIMAL_TEST})
    result = _parse_llm_response(raw)
    assert result["test_count"] == 1


def test_parse_llm_response_strips_markdown_fences():
    raw = "```json\n" + json.dumps({"test_code": MINIMAL_TEST}) + "\n```"
    result = _parse_llm_response(raw)
    assert result["test_code"] == MINIMAL_TEST


def test_parse_llm_response_raises_on_invalid_json():
    with pytest.raises(RuntimeError, match="non parsable"):
        _parse_llm_response("this is not json")


def test_parse_llm_response_raises_on_missing_test_code():
    raw = json.dumps({"filename": "test.py", "explanation": "no code"})
    with pytest.raises(RuntimeError, match="test_code"):
        _parse_llm_response(raw)


def test_parse_llm_response_raises_on_syntax_error_in_test_code():
    invalid_test = "def test_broken(:\n    pass\n"
    raw = json.dumps({"test_code": invalid_test})
    with pytest.raises(RuntimeError, match="syntaxe"):
        _parse_llm_response(raw)


def test_parse_llm_response_explanation_defaults_to_empty():
    raw = json.dumps({"test_code": MINIMAL_TEST})
    result = _parse_llm_response(raw)
    assert result["explanation"] == ""


# ─────────────────────────────────────────────────────────────────────────────
# _run_pytest
# ─────────────────────────────────────────────────────────────────────────────

def test_run_pytest_passes_on_trivial_test():
    test_code = "def test_always_passes():\n    assert True\n"
    result = _run_pytest(test_code)
    assert result["passed"] is True
    assert result["returncode"] == 0


def test_run_pytest_fails_on_failing_test():
    test_code = "def test_always_fails():\n    assert False, 'intentional failure'\n"
    result = _run_pytest(test_code)
    assert result["passed"] is False
    assert result["returncode"] != 0


def test_run_pytest_returns_stdout():
    test_code = "def test_x():\n    assert 1 + 1 == 2\n"
    result = _run_pytest(test_code)
    assert isinstance(result["stdout"], str)


def test_run_pytest_returns_non_empty_summary():
    test_code = "def test_x():\n    assert True\n"
    result = _run_pytest(test_code)
    assert result["summary"]  # non vide


def test_run_pytest_syntax_error_in_test_code():
    bad_test = "def test_broken(:\n    pass\n"
    result = _run_pytest(bad_test)
    assert result["passed"] is False
    assert result["syntax_errors"]


def test_run_pytest_failed_summary_mentions_failure():
    test_code = "def test_fail():\n    assert False\n"
    result = _run_pytest(test_code)
    summary = result["summary"].lower()
    assert "fail" in summary or "error" in summary


# ─────────────────────────────────────────────────────────────────────────────
# generate_tests — code entrant syntaxiquement invalide
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_tests_rejects_invalid_syntax():
    result = generate_tests("def bad(:\n    pass\n")
    assert result["syntax_ok"] is False
    assert result["syntax_errors"]
    assert result["pytest_result"]["passed"] is False
    assert result["generation_mode"] == "error"
    assert result["test_count"] == 0
    assert result["filename"] == ""


# ─────────────────────────────────────────────────────────────────────────────
# generate_tests — chemin simulation (LLM non disponible)
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_tests_simulation_returns_expected_fields(vulnerable_code):
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "", "mocked": True}
        result = generate_tests(vulnerable_code)

    assert result["mocked"] is True
    assert result["generation_mode"] == "simulation"
    assert result["syntax_ok"] is True
    assert "def test_" in result["test_code"]
    assert result["test_count"] >= 1
    assert "simulation" in result["explanation"].lower()
    assert "simulation" in result["filename"]


def test_generate_tests_simulation_tests_pass_on_clean_code():
    """
    Les tests de simulation generés sur du code PROPRE (sans eval()) doivent passer.
    Note : sur du code vulnérable (avec eval()), le test test_refactored_code_has_no_bare_eval
    échoue intentionnellement — c'est le comportement attendu.
    """
    clean_code = (
        "import os\n\n"
        "def get_user(user_id):\n"
        '    password = os.getenv("PASSWORD")\n'
        '    query = "SELECT * FROM users WHERE id = ?"\n'
        "    query_params = (user_id,)\n"
        "    cursor.execute(query, query_params)\n"
        "    try:\n"
        "        uid = int(user_id)\n"
        "    except ValueError as exc:\n"
        '        raise ValueError(f"Invalid ID") from exc\n'
        "    return query, password\n"
    )
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "", "mocked": True}
        result = generate_tests(clean_code)

    pr = result["pytest_result"]
    assert pr["passed"] is True, (
        f"Les tests de simulation ont échoué.\n"
        f"returncode={pr['returncode']}\n"
        f"summary={pr['summary']}\n"
        f"stdout=\n{pr['stdout']}\n"
        f"stderr=\n{pr['stderr']}\n"
        f"test_code=\n{result['test_code']}"
    )


def test_generate_tests_simulation_has_pytest_result(vulnerable_code):
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "", "mocked": True}
        result = generate_tests(vulnerable_code)

    pr = result["pytest_result"]
    assert "passed" in pr
    assert "stdout" in pr
    assert "summary" in pr
    assert "returncode" in pr


def test_generate_tests_simulation_message_is_not_generic_string():
    """La simulation ne doit PAS retourner l'ancien message statique."""
    simple = "def add(a, b):\n    return a + b\n"
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "", "mocked": True}
        result = generate_tests(simple)

    # L'ancien message statique ne doit plus apparaître
    assert "pas de vrais tests générés (LLM_API_URL non configuré)" not in result["explanation"]
    # La simulation doit être clairement identifiée
    assert "simulation" in result["explanation"].lower()


def test_generate_tests_simulation_detects_function_name():
    code = "def my_func():\n    return 42\n"
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "", "mocked": True}
        result = generate_tests(code)

    assert "my_func" in result["test_code"]


# ─────────────────────────────────────────────────────────────────────────────
# generate_tests — chemin LLM réel (réponse mockée valide)
# ─────────────────────────────────────────────────────────────────────────────

REAL_TEST_CODE = (
    "import pytest\n"
    "from unittest.mock import MagicMock, patch\n\n"
    "def test_get_user_returns_parameterized_query():\n"
    "    cursor = MagicMock()\n"
    "    with patch.dict('os.environ', {'PASSWORD': 'secret'}):\n"
    "        pass  # placeholder\n"
    "    assert cursor.call_count == 0\n\n"
    "def test_get_user_raises_valueerror_for_non_numeric_id():\n"
    "    with pytest.raises(ValueError):\n"
    "        int('not_a_number')\n"
)


def test_generate_tests_real_llm_returns_all_fields(vulnerable_code):
    fake_response = json.dumps({
        "filename": "test_get_user.py",
        "test_code": REAL_TEST_CODE,
        "test_count": 2,
        "explanation": "Tests couvrent la requête paramétrée et la validation de l'ID.",
    })
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": fake_response, "mocked": False}
        result = generate_tests(vulnerable_code)

    assert result["mocked"] is False
    assert result["generation_mode"] == "llm"
    assert result["filename"] == "test_get_user.py"
    assert result["test_code"] == REAL_TEST_CODE
    assert result["test_count"] == 2
    assert "paramétrée" in result["explanation"]
    assert result["syntax_ok"] is True


def test_generate_tests_real_llm_runs_pytest(vulnerable_code):
    fake_response = json.dumps({
        "test_code": "def test_x():\n    assert True\n",
    })
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": fake_response, "mocked": False}
        result = generate_tests(vulnerable_code)

    assert result["pytest_result"]["passed"] is True


def test_generate_tests_real_llm_failing_tests_reported(vulnerable_code):
    fake_response = json.dumps({
        "test_code": "def test_fail():\n    assert False\n",
    })
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": fake_response, "mocked": False}
        result = generate_tests(vulnerable_code)

    assert result["pytest_result"]["passed"] is False
    assert result["pytest_result"]["returncode"] != 0


def test_generate_tests_real_llm_invalid_json_raises(vulnerable_code):
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": "not json at all", "mocked": False}
        with pytest.raises(RuntimeError, match="non parsable"):
            generate_tests(vulnerable_code)


def test_generate_tests_real_llm_missing_test_code_raises(vulnerable_code):
    bad_response = json.dumps({"filename": "test.py", "explanation": "no code here"})
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": bad_response, "mocked": False}
        with pytest.raises(RuntimeError, match="test_code"):
            generate_tests(vulnerable_code)


def test_generate_tests_real_llm_syntax_error_in_generated_code_raises(vulnerable_code):
    """Si le LLM génère du code syntaxiquement invalide, RuntimeError doit être levée."""
    bad_test_code = "def test_broken(:\n    pass\n"
    bad_response = json.dumps({"test_code": bad_test_code})
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.return_value = {"content": bad_response, "mocked": False}
        with pytest.raises(RuntimeError, match="syntaxe"):
            generate_tests(vulnerable_code)


# ─────────────────────────────────────────────────────────────────────────────
# Propagation des erreurs API LLM
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_tests_propagates_llm_runtime_error(vulnerable_code):
    """
    Si call_llm lève RuntimeError (ex : clé manquante, HTTP 401, timeout),
    generate_tests doit laisser l'exception remonter — pas de simulation silencieuse.
    """
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.side_effect = RuntimeError("Authentification refusée (401)")
        with pytest.raises(RuntimeError, match="401"):
            generate_tests(vulnerable_code)


def test_generate_tests_propagates_connection_error(vulnerable_code):
    """
    Si call_llm lève RuntimeError (connexion impossible), generate_tests
    doit propager l'erreur sans basculer silencieusement en simulation.
    """
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.side_effect = RuntimeError("Impossible de joindre l'endpoint IBM Bob 2.0")
        with pytest.raises(RuntimeError, match="IBM Bob"):
            generate_tests(vulnerable_code)


def test_generate_tests_propagates_quota_error(vulnerable_code):
    with patch("backend.Agent6.test_generator_agent.call_llm") as mock_llm:
        mock_llm.side_effect = RuntimeError("Quota API dépassé (429)")
        with pytest.raises(RuntimeError, match="429"):
            generate_tests(vulnerable_code)
