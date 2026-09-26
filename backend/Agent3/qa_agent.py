"""
Agent 3 : Codebase Q&A Copilot Agent
-------------------------------------
Répond aux questions du développeur en utilisant
le code du projet indexé par l'Agent 1.
"""

from backend.Agent1.rag import query_index
from backend.Agent2.llm_client import call_llm


SYSTEM_PROMPT = """
Tu es un assistant expert en compréhension de code.

Ton rôle est d'aider un développeur à comprendre
un projet logiciel qu'il découvre.

Tu dois répondre uniquement à partir des extraits
de code fournis dans le contexte.

Règles :
- Ne pas inventer de fichiers, fonctions ou comportements.
- Si l'information n'est pas présente dans les extraits,
  indique clairement que tu ne peux pas la déterminer.
- Explique les choses simplement et précisément.
- Cite les fichiers pertinents dans ta réponse lorsque
  l'information est disponible.
- Réponds en français.
"""


def answer_question(
    project_id: str,
    question: str,
    n_results: int = 5
) -> dict:
    """
    Répond à une question du développeur en utilisant le RAG de l'Agent 1.
    Retourne {"answer": str, "mocked": bool}.
    """

    # 1. Recherche dans ChromaDB
    matches = query_index(
        project_id,
        question,
        n_results=n_results
    )

    # 2. Aucun résultat trouvé — pas besoin d'appeler le LLM
    if not matches:
        return {
            "answer": (
                "Je n'ai trouvé aucun extrait pertinent "
                "dans le code indexé pour répondre à cette question."
            ),
            "mocked": False,
        }

    # 3. Préparer les extraits trouvés
    context_blocks = []

    for match in matches:
        metadata = match.get("metadata", {})
        file_path = metadata.get("file_path", "Fichier inconnu")
        text = match.get("text", "")

        context_blocks.append(
            f"""
--- Fichier : {file_path} ---

{text}
"""
        )

    # 4. Regrouper tous les extraits
    context = "\n".join(context_blocks)

    # 5. Construire la question envoyée au LLM
    user_prompt = f"""
Voici les extraits du projet trouvés par le système RAG :

{context}

Question du développeur :

{question}

Réponds à la question uniquement à partir
des extraits fournis.

Indique les fichiers concernés lorsque c'est pertinent.
"""

    # 6. Envoyer le contexte + la question à IBM Bob 2.0
    #    call_llm() retourne {"content": str, "mocked": bool}
    result = call_llm(SYSTEM_PROMPT, user_prompt)

    # 7. Retourner la réponse dans le même format que les autres agents
    return {"answer": result["content"], "mocked": result["mocked"]}