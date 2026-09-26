"""
conftest.py — Configuration globale de pytest.

- Ajoute la racine du projet au PYTHONPATH pour que les imports
  `from backend.X import Y` fonctionnent.
- Injecte FORCE_MOCK_LLM=true et une LLM_API_KEY factice pour que
  les tests ne dépendent PAS d'une vraie connexion IBM Bob 2.0.
- Fournit les fixtures réutilisables entre tous les modules de tests.
"""

import os
import sys

# ── PYTHONPATH : ajouter la racine du projet ──────────────────────────────────
# Nécessaire pour que `from backend.Agent4.security_quality_agent import ...`
# fonctionne quel que soit le répertoire depuis lequel pytest est lancé.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Variables d'environnement pour les tests ─────────────────────────────────
# On force le mode mock (pas de vraie clé IBM requise) ET on injecte une clé
# factice pour contourner le premier check `if not LLM_API_KEY` du llm_client.
os.environ.setdefault("FORCE_MOCK_LLM", "true")
os.environ.setdefault("LLM_API_KEY", "test-fake-key-for-pytest")

import pytest


# ── Fixtures communes ─────────────────────────────────────────────────────────

@pytest.fixture
def vulnerable_code() -> str:
    """Code volontairement vulnérable utilisé dans tous les tests d'intégration."""
    return (
        'def get_user(user_id):\n'
        '    password = "admin123"\n'
        '    query = "SELECT * FROM users WHERE id = " + user_id\n'
        '    result = eval(user_id)\n'
        '    return query, password, result\n'
    )


@pytest.fixture
def sec002_finding() -> dict:
    """Finding SEC002 (credential hardcodé) minimal."""
    return {
        "rule_id": "SEC002",
        "title": "Hardcoded credential",
        "severity": "high",
        "category": "security",
        "line": 2,
        "code": 'password = "admin123"',
        "recommendation": "Load secrets from environment variables or a secret manager.",
    }


@pytest.fixture
def sec003_finding() -> dict:
    """Finding SEC003 (eval dangereux) minimal."""
    return {
        "rule_id": "SEC003",
        "title": "Dangerous dynamic execution",
        "severity": "high",
        "category": "security",
        "line": 4,
        "code": "result = eval(user_id)",
        "recommendation": (
            "Avoid dynamic execution of untrusted input; "
            "use a safe parser or an explicit allowlist."
        ),
    }
