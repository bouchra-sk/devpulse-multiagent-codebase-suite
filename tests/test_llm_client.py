"""
Tests pour le client LLM (Agent 2 : llm_client.py).

Vérifient :
  - Mode mock : retourne mocked=True sans appel HTTP
  - Mode réel : appelle requests.post avec les bons paramètres
  - Gestion d'erreurs HTTP (401, 429, 500, etc.)
  - Extraction correcte de la réponse OpenAI-compatible
  - Messages d'erreur actionnables (sans clé dans les logs)
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.Agent2 import llm_client as llm_module


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.ok = (status_code < 400)
    response.json.return_value = json_data or {
        "choices": [{"message": {"content": "Réponse du LLM"}}]
    }
    response.text = "OK"
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Mode mock (FORCE_MOCK_LLM=true ou LLM_API_URL absent)
# ─────────────────────────────────────────────────────────────────────────────

def test_call_llm_returns_mocked_when_no_url():
    """Sans LLM_API_URL, call_llm doit retourner mocked=True sans appel HTTP."""
    with (
        patch.object(llm_module, "LLM_API_URL", None),
        patch.object(llm_module, "LLM_API_KEY", "fake-key"),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
        patch("backend.Agent2.llm_client.requests.post") as mock_post,
    ):
        result = llm_module.call_llm("system", "user")

    assert result["mocked"] is True
    mock_post.assert_not_called()


def test_call_llm_returns_mocked_when_force_mock_true():
    """Avec FORCE_MOCK_LLM=True, call_llm doit retourner mocked=True."""
    with (
        patch.object(llm_module, "FORCE_MOCK_LLM", True),
        patch.object(llm_module, "LLM_API_KEY", "fake-key"),
        patch.object(llm_module, "LLM_API_URL", "http://fake-url"),
        patch("backend.Agent2.llm_client.requests.post") as mock_post,
    ):
        result = llm_module.call_llm("system", "user")

    assert result["mocked"] is True
    mock_post.assert_not_called()


def test_call_llm_mock_content_is_string():
    with (
        patch.object(llm_module, "LLM_API_URL", None),
        patch.object(llm_module, "LLM_API_KEY", "fake-key"),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
    ):
        result = llm_module.call_llm("system", "user")

    assert isinstance(result["content"], str)
    assert len(result["content"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Vérification des clés manquantes
# ─────────────────────────────────────────────────────────────────────────────

def test_call_llm_raises_when_api_key_missing():
    """Sans LLM_API_KEY, call_llm doit lever RuntimeError."""
    with (
        patch.object(llm_module, "LLM_API_KEY", None),
        patch.object(llm_module, "LLM_API_URL", "http://fake-url"),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
    ):
        with pytest.raises(RuntimeError, match="LLM_API_KEY"):
            llm_module.call_llm("system", "user")


def test_call_llm_raises_when_model_missing():
    """Sans LLM_MODEL, call_llm doit lever RuntimeError (en mode réel)."""
    with (
        patch.object(llm_module, "LLM_API_KEY", "fake-key"),
        patch.object(llm_module, "LLM_API_URL", "http://fake-url"),
        patch.object(llm_module, "LLM_MODEL", None),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
    ):
        with pytest.raises(RuntimeError, match="LLM_MODEL"):
            llm_module.call_llm("system", "user")


# ─────────────────────────────────────────────────────────────────────────────
# Mode réel : appel HTTP réussi
# ─────────────────────────────────────────────────────────────────────────────

def test_call_llm_real_mode_returns_content():
    """En mode réel, call_llm doit extraire le contenu de la réponse OpenAI."""
    mock_response = _make_mock_response(200, {
        "choices": [{"message": {"content": "Voici le correctif"}}]
    })
    with (
        patch.object(llm_module, "LLM_API_KEY", "fake-key"),
        patch.object(llm_module, "LLM_API_URL", "http://fake-url/chat"),
        patch.object(llm_module, "LLM_MODEL", "ibm/granite-3-8b-instruct"),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
        patch("backend.Agent2.llm_client.requests.post", return_value=mock_response),
    ):
        result = llm_module.call_llm("system", "user")

    assert result["mocked"] is False
    assert result["content"] == "Voici le correctif"


def test_call_llm_real_mode_sends_correct_payload():
    """Vérifie que le payload envoyé à l'API est correct."""
    mock_response = _make_mock_response()
    with (
        patch.object(llm_module, "LLM_API_KEY", "fake-key"),
        patch.object(llm_module, "LLM_API_URL", "http://fake-url/chat"),
        patch.object(llm_module, "LLM_MODEL", "my-model"),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
        patch("backend.Agent2.llm_client.requests.post", return_value=mock_response) as mock_post,
    ):
        llm_module.call_llm("sys_prompt", "usr_prompt", temperature=0.5)

    called_kwargs = mock_post.call_args
    payload = called_kwargs.kwargs.get("json") or called_kwargs.args[1]
    assert payload["model"] == "my-model"
    assert payload["temperature"] == 0.5
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "sys_prompt"
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"] == "usr_prompt"


def test_call_llm_real_mode_sends_authorization_header():
    mock_response = _make_mock_response()
    with (
        patch.object(llm_module, "LLM_API_KEY", "my-secret-key"),
        patch.object(llm_module, "LLM_API_URL", "http://fake-url/chat"),
        patch.object(llm_module, "LLM_MODEL", "my-model"),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
        patch("backend.Agent2.llm_client.requests.post", return_value=mock_response) as mock_post,
    ):
        llm_module.call_llm("s", "u")

    headers = mock_post.call_args.kwargs.get("headers") or mock_post.call_args.args[1]
    assert headers["Authorization"] == "Bearer my-secret-key"


# ─────────────────────────────────────────────────────────────────────────────
# Mode réel : gestion des erreurs HTTP
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status_code,expected_fragment", [
    (401, "401"),
    (429, "429"),
    (500, "500"),
])
def test_call_llm_raises_on_http_errors(status_code, expected_fragment):
    mock_response = _make_mock_response(status_code)
    mock_response.ok = False
    with (
        patch.object(llm_module, "LLM_API_KEY", "fake-key"),
        patch.object(llm_module, "LLM_API_URL", "http://fake-url/chat"),
        patch.object(llm_module, "LLM_MODEL", "my-model"),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
        patch("backend.Agent2.llm_client.requests.post", return_value=mock_response),
    ):
        with pytest.raises(RuntimeError, match=expected_fragment):
            llm_module.call_llm("s", "u")


def test_call_llm_raises_on_unexpected_response_format():
    """Si la réponse ne suit pas le format OpenAI, lever RuntimeError."""
    mock_response = _make_mock_response(200, {"unexpected": "format"})
    with (
        patch.object(llm_module, "LLM_API_KEY", "fake-key"),
        patch.object(llm_module, "LLM_API_URL", "http://fake-url/chat"),
        patch.object(llm_module, "LLM_MODEL", "my-model"),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
        patch("backend.Agent2.llm_client.requests.post", return_value=mock_response),
    ):
        with pytest.raises(RuntimeError, match="Format de réponse inattendu"):
            llm_module.call_llm("s", "u")


# ─────────────────────────────────────────────────────────────────────────────
# Mode réel : gestion des erreurs réseau
# ─────────────────────────────────────────────────────────────────────────────

def test_call_llm_raises_on_timeout():
    import requests as req_lib
    with (
        patch.object(llm_module, "LLM_API_KEY", "fake-key"),
        patch.object(llm_module, "LLM_API_URL", "http://fake-url/chat"),
        patch.object(llm_module, "LLM_MODEL", "my-model"),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
        patch("backend.Agent2.llm_client.requests.post", side_effect=req_lib.exceptions.Timeout()),
    ):
        with pytest.raises(RuntimeError, match="Délai"):
            llm_module.call_llm("s", "u")


def test_call_llm_raises_on_connection_error():
    import requests as req_lib
    with (
        patch.object(llm_module, "LLM_API_KEY", "fake-key"),
        patch.object(llm_module, "LLM_API_URL", "http://fake-url/chat"),
        patch.object(llm_module, "LLM_MODEL", "my-model"),
        patch.object(llm_module, "FORCE_MOCK_LLM", False),
        patch("backend.Agent2.llm_client.requests.post",
              side_effect=req_lib.exceptions.ConnectionError("refused")),
    ):
        with pytest.raises(RuntimeError, match="joindre"):
            llm_module.call_llm("s", "u")
