"""
Configuration : cherche la clé API et l'URL du LLM (IBM Bob 2.0) parmi
plusieurs noms de variables possibles, car selon l'IDE/le hackathon elles
peuvent être injectées sous des noms différents. Charge aussi un .env
si présent (utile en local).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Plusieurs noms candidats — on prend le premier qui existe et n'est pas vide.
_URL_CANDIDATES = [
    "LLM_API_URL", "BOB_API_URL", "IBM_BOB_URL",
    "WATSONX_URL", "WX_URL", "AI_API_URL",
]
_KEY_CANDIDATES = [
    "LLM_API_KEY", "BOB_API_KEY", "IBM_BOB_KEY",
    "WATSONX_APIKEY", "WATSONX_API_KEY", "API_KEY", "SECRET_KEY",
]


def _first_set(names: list[str]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


LLM_API_KEY = _first_set(_KEY_CANDIDATES)
LLM_API_URL = _first_set(_URL_CANDIDATES)

# Requis par le proxy LiteLLM d'IBM Bob 2.0 (confirmé par sa doc) — le
# champ "model" doit être envoyé dans le payload de chaque appel.
LLM_MODEL = _first_set(["LLM_MODEL", "BOB_MODEL", "MODEL_ID", "MODEL"])

# Spécifique watsonx.ai : en plus de la clé + l'URL, il faut un project_id.
# Reste None tant que tu ne l'as pas obtenu des organisateurs — dans ce cas
# le SDK watsonx n'est simplement pas utilisé (fallback sur requests brut,
# ou mode simulation).
WATSONX_PROJECT_ID = _first_set(["WATSONX_PROJECT_ID", "PROJECT_ID"])
WATSONX_MODEL_ID = os.getenv("WATSONX_MODEL_ID", "ibm/granite-3-8b-instruct")

# Force le mode simulation même si une URL est trouvée plus tard
# (mets FORCE_MOCK_LLM=true dans .env pour économiser ton quota API).
FORCE_MOCK_LLM = os.getenv("FORCE_MOCK_LLM", "false").lower() == "true"

if not LLM_API_KEY:
    print(f"⚠️  Aucune clé API trouvée parmi {_KEY_CANDIDATES}.")

if not LLM_API_URL:
    print(
        f"⚠️  Aucune URL LLM trouvée parmi {_URL_CANDIDATES} — "
        "mode simulation actif tant que tu ne l'auras pas configurée."
    )
elif not LLM_MODEL:
    print(
        "⚠️  LLM_API_URL est configuré mais LLM_MODEL est absent — "
        "le proxy LiteLLM d'IBM Bob 2.0 exige ce champ, récupère "
        "l'identifiant du modèle sur ton portail hackathon."
    )
elif not WATSONX_PROJECT_ID:
    print(
        "ℹ️  LLM_API_URL est configuré mais WATSONX_PROJECT_ID est absent — "
        "si ton backend est watsonx.ai, il te faudra aussi ce project_id "
        "(demande-le aux organisateurs)."
    )