"""
Client générique pour appeler le LLM (IBM Bob 2.0).

Pendant le hackathon, si LLM_API_URL n'est pas encore connu (ou si
FORCE_MOCK_LLM=true dans .env), ce module bascule en MODE SIMULATION :
il renvoie une réponse factice GÉNÉRIQUE, pour que tu puisses développer
et tester le reste du pipeline (Agent 2, Agent 3, Streamlit) sans être
bloqué.

⚠️ Ce mock est volontairement générique (pas de texte "architecture" codé
en dur) car call_llm() est partagé par TOUS les agents — l'Agent 3 (Q&A)
l'utilise aussi, avec un prompt complètement différent de l'Agent 2.

⚠️ Le mode simulation est signalé dans les logs ET dans le champ "mocked"
du résultat, pour ne jamais confondre une vraie réponse d'IBM Bob 2.0
avec une réponse simulée (risque réel le jour de la démo).
"""

import requests
from backend.config import LLM_API_KEY, LLM_API_URL, FORCE_MOCK_LLM


def _is_mock_mode() -> bool:
    return FORCE_MOCK_LLM or not LLM_API_URL


def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> dict:
    """
    Retourne {"content": str, "mocked": bool}.

    On retourne un dict (et pas juste une str) pour que l'appelant sache
    TOUJOURS si la réponse vient réellement d'IBM Bob 2.0 ou d'une
    simulation — important à afficher côté Streamlit pendant le hackathon.
    """
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY manquant dans .env")

    if _is_mock_mode():
        print("⚠️  [MOCK MODE] LLM_API_URL absent ou FORCE_MOCK_LLM=true — réponse simulée.")
        return {
            "content": (
                "(Réponse simulée — LLM_API_URL n'est pas encore configuré. "
                "Le pipeline fonctionne correctement, mais ceci n'est pas une "
                "vraie réponse d'IBM Bob 2.0.)\n\n"
                f"Prompt reçu (premiers 200 caractères) : {user_prompt[:200]}..."
            ),
            "mocked": True,
        }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    # À ce stade on n'est plus en mock mode, donc LLM_API_URL est forcément
    # défini (_is_mock_mode() l'a vérifié) — cet assert le confirme aussi
    # explicitement au type checker (narrowing de "str | None" vers "str").
    assert LLM_API_URL is not None, "LLM_API_URL devrait être défini ici (bug de logique sinon)"

    response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    # 👇 À ajuster si la structure réelle de la réponse d'IBM Bob 2.0 diffère
    content = data["choices"][0]["message"]["content"]
    return {"content": content, "mocked": False}