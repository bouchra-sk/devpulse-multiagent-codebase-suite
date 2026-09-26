
import json
import re
 
from backend.Agent2.llm_client import call_llm
 
SYSTEM_PROMPT = """Tu es un Senior Software Engineer spécialisé en sécurité
et en Clean Code. On te donne un extrait de code et un rapport d'audit
listant des problèmes de sécurité et de qualité détectés dessus.
 
Ta mission :
1. Corriger TOUS les problèmes listés dans le rapport.
2. Garder le comportement fonctionnel du code identique (ne pas ajouter
   de nouvelles fonctionnalités, ne rien retirer qui n'est pas listé).
3. Respecter les principes du Clean Code (nommage clair, fonctions
   courtes, gestion d'erreurs explicite).
 
Réponds UNIQUEMENT avec un objet JSON de cette forme, sans texte autour,
sans balises markdown :
{
  "refactored_code": "<le code corrigé complet>",
  "changes_summary": "<résumé en 2-4 phrases des changements effectués>"
}
"""
 
 
def _format_findings(findings: list[dict]) -> str:
    if not findings:
        return "Aucun problème détecté par l'Agent 1."
    lines = []
    for f in findings:
        lines.append(
            f"- [{f['severity'].upper()}] {f['rule_id']} — {f['title']} "
            f"(ligne {f['line']}) : {f['recommendation']}"
        )
    return "\n".join(lines)
 
 
def _parse_json_response(raw: str) -> dict:
    """
    Extrait le JSON de la réponse du LLM, même si celui-ci l'a entouré
    de ```json ... ``` malgré la consigne (ça arrive souvent en pratique,
    mieux vaut nettoyer que planter).
    """
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Réponse du LLM non parsable en JSON : {e}\nRéponse brute : {raw[:300]}"
        )
 
    if "refactored_code" not in data:
        raise RuntimeError("La réponse du LLM ne contient pas 'refactored_code'.")
 
    return {
        "refactored_code": data["refactored_code"],
        "changes_summary": data.get("changes_summary", ""),
    }
 
 
def refactor_code(code: str, findings: list[dict]) -> dict:
    """
    Orchestration de l'Agent 2.
    Retourne {"refactored_code": str, "changes_summary": str, "mocked": bool}.
    """
    user_prompt = f"""CODE ORIGINAL :
```
{code}
```
 
RAPPORT DE L'AGENT 1 (problèmes à corriger) :
{_format_findings(findings)}
 
Génère maintenant le JSON demandé."""
 
    result = call_llm(SYSTEM_PROMPT, user_prompt, temperature=0.2)
 
    if result["mocked"]:
        # En mode simulation il n'y a pas de vrai JSON à parser : on renvoie
        # le code original tel quel pour que le pipeline ne casse pas.
        return {
            "refactored_code": code,
            "changes_summary": (
                "(Mode simulation — aucun refactoring réel effectué, "
                "LLM_API_URL non configuré.)"
            ),
            "mocked": True,
        }
 
    parsed = _parse_json_response(result["content"])
    parsed["mocked"] = False
    return parsed