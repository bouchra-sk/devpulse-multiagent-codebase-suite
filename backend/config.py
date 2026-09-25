"""
Configuration : charge la clé secrète (IBM Bob 2.0) et l'URL de l'API
depuis un fichier .env.
"""

import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_API_URL = os.getenv("LLM_API_URL")  # peut être absent tant que tu ne l'as pas trouvé

# Permet de forcer explicitement le mode simulation dans .env
# (FORCE_MOCK_LLM=true), utile même une fois l'URL trouvée, pour développer
# sans consommer de quota API.
FORCE_MOCK_LLM = os.getenv("FORCE_MOCK_LLM", "false").lower() == "true"

if not LLM_API_KEY:
    print("⚠️  LLM_API_KEY manquant dans .env.")

if not LLM_API_URL:
    print(
        "⚠️  LLM_API_URL manquant dans .env — llm_client tournera en "
        "MODE SIMULATION (réponses factices) tant que tu ne l'auras pas."
    )