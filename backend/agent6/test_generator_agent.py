
import json
import re
 
from backend.Agent2.llm_client import call_llm
 
SYSTEM_PROMPT = """Tu es un ingénieur QA spécialisé en tests automatisés Python.
On te donne un extrait de code déjà corrigé et sécurisé. Génère un fichier
de tests PyTest complet et exécutable qui couvre :
- les cas d'utilisation normaux (happy path)
- au moins un cas limite (edge case) par fonction publique
- les cas d'erreur attendus (exceptions)
 
Réponds UNIQUEMENT avec un objet JSON de cette forme, sans texte autour,
sans balises markdown :
{
  "test_code": "<le fichier de tests PyTest complet, imports inclus>"
}
"""
 
 
def generate_tests(refactored_code: str) -> dict:
    """
    Orchestration de l'Agent 3.
    Retourne {"test_code": str, "mocked": bool}.
    """
    user_prompt = f"""CODE À TESTER :
```
{refactored_code}
```
 
Génère maintenant le JSON demandé."""
 
    result = call_llm(SYSTEM_PROMPT, user_prompt, temperature=0.2)
 
    if result["mocked"]:
        return {
            "test_code": (
                "# (Mode simulation — LLM_API_URL non configuré, "
                "aucun test réel généré.)\n"
            ),
            "mocked": True,
        }
 
    cleaned = re.sub(
        r"^```(?:json)?|```$", "", result["content"].strip(), flags=re.MULTILINE
    ).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Réponse du LLM non parsable en JSON : {e}\n"
            f"Réponse brute : {result['content'][:300]}"
        )
 
    if "test_code" not in data:
        raise RuntimeError("La réponse du LLM ne contient pas 'test_code'.")
 
    return {"test_code": data["test_code"], "mocked": False}