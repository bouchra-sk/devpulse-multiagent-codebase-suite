"""
Client générique pour appeler le LLM (IBM Bob 2.0 — proxy LiteLLM,
compatible format OpenAI, confirmé par la doc officielle d'IBM Bob).

Mode réel : LLM_API_URL + LLM_API_KEY + LLM_MODEL définis dans .env
Mode mock : LLM_API_URL absent, OU FORCE_MOCK_LLM=true dans .env
"""

import requests
from backend.config import LLM_API_KEY, LLM_API_URL, LLM_MODEL, FORCE_MOCK_LLM


def _is_mock_mode() -> bool:
    return FORCE_MOCK_LLM or not LLM_API_URL


def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> dict:
    """
    Retourne {"content": str, "mocked": bool}.
    Lève RuntimeError avec un message actionnable si la config est
    incomplète ou si l'API répond avec une erreur.
    """
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY manquant dans .env — génère une clé Inference sur bob.ibm.com."
        )

    if _is_mock_mode():
        print("⚠️  [MOCK MODE] LLM_API_URL absent ou FORCE_MOCK_LLM=true — réponse simulée.")
        return {
            "content": (
                "Mode simulation — IBM Bob 2.0 n'est pas encore connecté "
                "(LLM_API_URL absent dans .env). Le pipeline fonctionne "
                "correctement, mais ceci n'est pas une vraie réponse générée."
            ),
            "mocked": True,
        }

    # Mode réel : LLM_MODEL est obligatoire (exigé par le proxy LiteLLM)
    if not LLM_MODEL:
        raise RuntimeError(
            "LLM_MODEL manquant dans .env — renseigne l'identifiant du "
            "modèle fourni dans ton portail hackathon."
        )

    # À ce stade on n'est plus en mock mode, donc LLM_API_URL est forcément
    # défini (_is_mock_mode() l'a vérifié) — confirmé explicitement au type
    # checker (narrowing de "str | None" vers "str").
    assert LLM_API_URL is not None, "LLM_API_URL devrait être défini ici (bug de logique sinon)"

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,  # requis par le proxy LiteLLM d'IBM Bob 2.0
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    try:
        response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=60)
    except requests.exceptions.Timeout:
        raise RuntimeError("Délai dépassé (60s) lors de l'appel à IBM Bob 2.0 — réessaie.")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Impossible de joindre l'endpoint IBM Bob 2.0 : {e}")

    # Erreurs HTTP explicites — jamais de clé affichée dans les messages
    if response.status_code == 401:
        raise RuntimeError(
            "Authentification refusée (401) — vérifie que LLM_API_KEY est "
            "correct et de type Inference."
        )
    if response.status_code == 429:
        raise RuntimeError(
            "Quota API dépassé (429) — attends quelques instants avant de réessayer."
        )
    if response.status_code >= 500:
        raise RuntimeError(
            f"Erreur serveur IBM Bob 2.0 ({response.status_code}) — "
            "l'API est peut-être temporairement indisponible."
        )
    if not response.ok:
        raise RuntimeError(
            f"Erreur inattendue de l'API ({response.status_code}) : {response.text[:200]}"
        )

    data = response.json()

    # Extraction sécurisée — le proxy LiteLLM retourne le format OpenAI-compatible
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(
            f"Format de réponse inattendu d'IBM Bob 2.0 (clé manquante : {e}). "
            f"Réponse reçue (premiers 300 car.) : {str(data)[:300]}"
        )

    return {"content": content, "mocked": False}