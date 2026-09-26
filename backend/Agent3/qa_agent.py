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

# Mots-clés qui indiquent une question sur le POINT D'ENTRÉE du projet.
# Pour ce type de question précis, pas besoin de LLM : on peut répondre
# directement et correctement en cherchant les noms de fichiers habituels
# dans l'arborescence déjà indexée par l'Agent 1.
_ENTRY_POINT_KEYWORDS = (
    "point d'entrée", "point d'entree", "entry point",
    "où commence", "ou commence", "comment lancer", "comment démarrer",
    "comment demarrer", "lancer le serveur", "démarrer le projet",
)

# Noms de fichiers usuels qui servent de point d'entrée selon le langage/framework.
_ENTRY_POINT_FILENAMES = (
    "main.py", "app.py", "manage.py", "run.py", "server.py",
    "index.js", "index.ts", "server.js",
)


def _is_entry_point_question(question: str) -> bool:
    q = question.lower()
    return any(keyword in q for keyword in _ENTRY_POINT_KEYWORDS)


def _find_entry_points_in_tree(folder_tree: str) -> list[str]:
    """
    Cherche les noms de fichiers point d'entrée usuels dans l'arborescence
    du projet (texte brut retourné par build_folder_tree). Retourne les
    lignes correspondantes telles qu'elles apparaissent dans l'arborescence.
    """
    found = []
    for line in folder_tree.splitlines():
        stripped = line.strip()
        for filename in _ENTRY_POINT_FILENAMES:
            if stripped.lower() == filename or stripped.lower().endswith("/" + filename):
                found.append(stripped)
    return found


def _build_entry_point_answer(folder_tree: str) -> str:
    """
    Construit une réponse structurée (3 sections, sans LLM) pour une
    question sur le point d'entrée, calculée directement depuis
    l'arborescence réelle du projet indexé.
    """
    entry_points = _find_entry_points_in_tree(folder_tree)

    if not entry_points:
        return (
            "1. Point d'entrée principal\n"
            "Aucun fichier point d'entrée usuel (main.py, app.py, manage.py...) "
            "n'a été trouvé dans l'arborescence indexée. Vérifie que le bon "
            "dossier a bien été indexé via /index.\n"
        )

    main_entry = entry_points[0]
    others = entry_points[1:]

    lines = [
        "1. Point d'entrée principal",
        f"Le point d'entrée principal détecté est `{main_entry}`.",
        "",
        "2. Fonctionnement",
        f"- C'est ce fichier qui doit être lancé pour démarrer l'application "
        f"(ex : `uvicorn {main_entry.replace('.py', '').replace('/', '.')}:app --reload` "
        "s'il s'agit d'un projet FastAPI).",
    ]
    if others:
        lines.append(
            f"- D'autres fichiers similaires ont aussi été détectés : {', '.join(others)}."
        )
    lines += [
        "",
        "3. Où modifier le code ?",
        f"Pour ajouter une nouvelle route ou modifier le comportement global, "
        f"consulte `{main_entry}`. Pour modifier un agent en particulier, "
        "ouvre son fichier dédié.",
        "",
        "(Réponse calculée directement depuis l'arborescence indexée, "
        "sans LLM — donc fiable même en mode simulation.)",
    ]
    return "\n".join(lines)


def answer_question(
    project_id: str,
    question: str,
    folder_tree: str | None = None,
    n_results: int = 5
) -> dict:
    """
    Répond à une question du développeur en utilisant le RAG de l'Agent 1.
    Retourne {"answer": str, "mocked": bool, "sources": list}.
    """

    # 0. Cas particulier : question sur le point d'entrée → réponse
    #    déterministe depuis l'arborescence, pas besoin de LLM ni de RAG.
    if folder_tree and _is_entry_point_question(question):
        return {
            "answer": _build_entry_point_answer(folder_tree),
            "mocked": False,  # ce n'est pas une simulation, c'est un vrai calcul
            "sources": [],
        }

    # 1. Recherche dans ChromaDB
    matches = query_index(project_id, question, n_results=n_results)

    # 2. Aucun résultat trouvé — pas besoin d'appeler le LLM
    if not matches:
        return {
            "answer": (
                "Je n'ai trouvé aucun extrait pertinent "
                "dans le code indexé pour répondre à cette question."
            ),
            "mocked": False,
            "sources": [],
        }

    # 3. Regrouper les chunks par fichier (un même fichier peut être découpé
    #    en plusieurs chunks — inutile d'afficher 3 fois le même nom de
    #    fichier avec des bouts différents, on les fusionne en une entrée).
    sources_by_file: dict[str, list[str]] = {}
    for match in matches:
        file_path = match.get("metadata", {}).get("file_path", "Fichier inconnu")
        snippet = match.get("text", "")[:500]
        sources_by_file.setdefault(file_path, []).append(snippet)

    sources = [
        {"file": file_path, "snippets": snippets}
        for file_path, snippets in sources_by_file.items()
    ]

    # 4. Préparer le contexte complet pour le LLM (texte entier, pas raccourci)
    context_blocks = [
        f"\n--- Fichier : {match.get('metadata', {}).get('file_path', 'Fichier inconnu')} ---\n\n"
        f"{match.get('text', '')}\n"
        for match in matches
    ]
    context = "\n".join(context_blocks)

    user_prompt = f"""
Voici les extraits du projet trouvés par le système RAG :

{context}

Question du développeur :

{question}

Réponds à la question uniquement à partir
des extraits fournis.

Indique les fichiers concernés lorsque c'est pertinent.
"""

    # 5. Envoyer le contexte + la question à IBM Bob 2.0
    result = call_llm(SYSTEM_PROMPT, user_prompt)

    # 6. En mode simulation : pas de wall of text, juste un message court +
    #    les extraits structurés (le frontend les affichera proprement).
    if result["mocked"]:
        return {
            "answer": (
                f"🔧 Mode simulation — extraits trouvés dans {len(sources)} "
                "fichier(s) pour ta question (affichés ci-dessous, regroupés "
                "par fichier). Une vraie synthèse arrivera une fois IBM Bob "
                "2.0 connecté."
            ),
            "mocked": True,
            "sources": sources,
        }

    # 7. Réponse réelle du LLM
    return {"answer": result["content"], "mocked": False, "sources": sources}