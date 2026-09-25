"""
Agent 2 : Architecture Summarizer Agent
------------------------------------------
Construit un résumé architectural complet du projet, en jouant le rôle
d'un architecte logiciel qui explique le projet à un nouveau développeur
(Meta-Prompting orienté rôle, IBM Bob 2.0).
"""

from backend.Agent1.rag import query_index
from llm_client import call_llm

# Questions génériques posées au RAG pour récupérer les chunks les plus
# pertinents pour comprendre l'architecture globale. Pas besoin d'envoyer
# tout le code au LLM — juste les extraits les plus représentatifs.
ARCHITECTURE_QUERIES = [
    "point d'entrée principal de l'application, fichier main",
    "configuration des routes ou des endpoints de l'API",
    "dépendances et technologies utilisées dans le projet",
    "structure générale des dossiers et modules",
]

# Meta-prompt : on donne au LLM le rôle d'un architecte logiciel qui
# explique le projet à un développeur qui le découvre pour la première fois.
SYSTEM_PROMPT = """Tu es un architecte logiciel (Software Architect) expérimenté.
Ton rôle est d'expliquer un projet de code à un nouveau développeur qui vient
de le découvrir. Ta réponse doit être claire, structurée et pédagogique, en français.

Structure ta réponse en 3 parties, avec ces titres exacts :

1. Organisation des dossiers et technologies utilisées
2. Points d'entrée du projet (Entry Points)
3. Comment naviguer et apporter des modifications

Base-toi uniquement sur l'arborescence et les extraits de code fournis.
Ne parle jamais d'informations que tu ne peux pas déduire du contexte donné.
"""


def gather_context(project_id: str, folder_tree: str) -> str:
    """
    Récupère les chunks les plus pertinents pour comprendre l'architecture,
    en interrogeant le RAG (construit par l'Agent 1) avec plusieurs questions
    génériques, puis dédoublonne par fichier pour ne pas répéter le même contenu.
    """
    seen_files = set()
    context_blocks = [f"ARBORESCENCE DU PROJET :\n{folder_tree}\n"]

    for query in ARCHITECTURE_QUERIES:
        matches = query_index(project_id, query, n_results=3)
        for match in matches:
            file_path = match["metadata"]["file_path"]
            if file_path in seen_files:
                continue
            seen_files.add(file_path)
            context_blocks.append(f"--- Extrait de {file_path} ---\n{match['text']}")

    return "\n\n".join(context_blocks)


def summarize_architecture(project_id: str, folder_tree: str) -> dict:
    """
    Orchestration complète de l'Agent 2 :
    1. Rassemble le contexte pertinent depuis le RAG (Agent 1)
    2. Envoie ce contexte au LLM avec le meta-prompt "architecte logiciel"
    3. Retourne {"content": str, "mocked": bool}, prêt à afficher dans Streamlit
    """
    context = gather_context(project_id, folder_tree)

    user_prompt = f"""Voici le contexte du projet à analyser :

{context}

Rédige maintenant le résumé architectural pour le nouveau développeur."""

    return call_llm(SYSTEM_PROMPT, user_prompt)