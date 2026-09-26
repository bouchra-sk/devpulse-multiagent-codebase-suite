
"""
Agent 3: Codebase Q&A Copilot Agent
-----------------------------------
Answers developer questions using the project
code indexed by Agent 1.
"""

from backend.Agent1.rag import query_index
from backend.Agent2.llm_client import call_llm


SYSTEM_PROMPT = """
You are an expert assistant in code understanding.

Your role is to help developers understand
a software project they are exploring.

You must answer only using the code excerpts
provided in the context.

Rules:
- Do not invent files, functions, or behaviors.
- If the information is not present in the excerpts,
  clearly state that you cannot determine it.
- Explain things simply and precisely.
- Cite relevant files in your answer whenever
  the information is available.
- Respond in the same language as the developer's question.
- If the question is in English, answer in English.
- If the question is in French, answer in French.
- If the question is in Arabic, answer in Arabic.
"""


# Keywords indicating a question about the project's ENTRY POINT.
# For this specific type of question, no LLM is required:
# we can answer directly by searching for common filenames
# in the project tree indexed by Agent 1.

_ENTRY_POINT_KEYWORDS = (
    "entry point",
    "main entry",
    "where does it start",
    "where to start",
    "how to run",
    "how to start",
    "start the server",
    "start the project",
    "main file",
    "point d'entrée",
    "point d'entree",
    "où commence",
    "ou commence",
    "comment lancer",
    "comment démarrer",
    "comment demarrer",
    "lancer le serveur",
    "démarrer le projet",
)


# Common entry point filenames depending on the
# programming language or framework.

_ENTRY_POINT_FILENAMES = (
    "main.py",
    "app.py",
    "manage.py",
    "run.py",
    "server.py",
    "index.js",
    "index.ts",
    "server.js",
)


def _is_entry_point_question(question: str) -> bool:
    q = question.lower()
    return any(
        keyword in q
        for keyword in _ENTRY_POINT_KEYWORDS
    )


def _find_entry_points_in_tree(
    folder_tree: str
) -> list[str]:
    """
    Search for common entry point filenames in the
    project tree returned by build_folder_tree.

    Returns the matching lines as they appear
    in the project tree.
    """

    found = []

    for line in folder_tree.splitlines():
        stripped = line.strip()

        for filename in _ENTRY_POINT_FILENAMES:
            if (
                stripped.lower() == filename
                or stripped.lower().endswith(
                    "/" + filename
                )
            ):
                found.append(stripped)

    return found


def _build_entry_point_answer(
    folder_tree: str,
    question: str
) -> str:
    """
    Build a structured answer about the entry point
    directly from the indexed project tree.

    No LLM is required for this operation.
    The response language is based on the question.
    """

    entry_points = _find_entry_points_in_tree(
        folder_tree
    )

    q = question.lower()

    # Detect the language of the question.
    english_keywords = (
        "where",
        "what",
        "how",
        "which",
        "main",
        "entry point",
        "start",
        "run",
        "launch",
        "project",
    )

    french_keywords = (
        "où",
        "ou",
        "comment",
        "lancer",
        "démarrer",
        "demarrer",
        "projet",
        "point d'entrée",
        "point d'entree",
    )

    is_english = any(
        word in q for word in english_keywords
    )

    is_french = any(
        word in q for word in french_keywords
    )

    if is_english:
        language = "en"
    elif is_french:
        language = "fr"
    else:
        language = "en"

    # No entry point found.
    if not entry_points:

        if language == "en":
            return (
                "1. Main Entry Point\n"
                "No common entry point file "
                "(main.py, app.py, manage.py, etc.) "
                "was found in the indexed project tree.\n"
                "Please check that the correct project "
                "was indexed using POST /index."
            )

        return (
            "1. Point d'entrée principal\n"
            "Aucun fichier point d'entrée usuel "
            "(main.py, app.py, manage.py, etc.) "
            "n'a été trouvé dans l'arborescence indexée.\n"
            "Vérifie que le bon projet a été indexé "
            "via POST /index."
        )

    main_entry = entry_points[0]
    others = entry_points[1:]

    # English response.
    if language == "en":

        lines = [
            "1. Main Entry Point",
            (
                f"The detected main entry point "
                f"is `{main_entry}`."
            ),
            "",
            "2. How it works",
            (
                f"- This file is associated with "
                f"starting the application."
            ),
            (
                f"- If it contains a FastAPI app, "
                f"you can run it using Uvicorn, "
                f"for example: `uvicorn "
                f"{main_entry.replace('.py', '').replace('/', '.')}"
                f":app --reload`."
            ),
        ]

        if others:
            lines.append(
                "- Other possible entry point files "
                "were also detected: "
                + ", ".join(others)
                + "."
            )

        lines += [
            "",
            "3. Where to modify the code",
            (
                f"To add a new route or modify "
                f"the application's global behavior, "
                f"check `{main_entry}`."
            ),
            (
                "To modify a specific agent, "
                "open its dedicated file."
            ),
            "",
            (
                "(This answer was generated directly "
                "from the indexed project tree, "
                "without using the LLM.)"
            ),
        ]

    # French response.
    else:

        lines = [
            "1. Point d'entrée principal",
            (
                f"Le point d'entrée détecté "
                f"est `{main_entry}`."
            ),
            "",
            "2. Fonctionnement",
            (
                f"- Ce fichier est associé au "
                f"démarrage de l'application."
            ),
            (
                f"- S'il contient une application "
                f"FastAPI, tu peux la lancer avec "
                f"Uvicorn, par exemple : `uvicorn "
                f"{main_entry.replace('.py', '').replace('/', '.')}"
                f":app --reload`."
            ),
            "",
            "3. Où modifier le code ?",
            (
                f"Pour ajouter une route ou modifier "
                f"le comportement global, consulte "
                f"`{main_entry}`."
            ),
            (
                "Pour modifier un agent particulier, "
                "ouvre son fichier dédié."
            ),
            "",
            (
                "(Cette réponse est calculée directement "
                "depuis l'arborescence indexée, "
                "sans utiliser le LLM.)"
            ),
        ]

    return "\n".join(lines)


def answer_question(
    project_id: str,
    question: str,
    folder_tree: str | None = None,
    n_results: int = 5
) -> dict:
    """
    Answer developer questions using Agent 1's RAG.

    Returns:
        {
            "answer": str,
            "mocked": bool,
            "sources": list
        }
    """

    # 0. Special case: entry point questions.
    # Answer directly from the project tree,
    # without calling the LLM or RAG.

    if (
        folder_tree
        and _is_entry_point_question(question)
    ):
        return {
            "answer": _build_entry_point_answer(
                folder_tree,
                question
            ),
            "mocked": False,
            "sources": [],
        }

    # 1. Search ChromaDB.
    matches = query_index(
        project_id,
        question,
        n_results=n_results
    )

    # 2. No results found.
    if not matches:
        return {
            "answer": (
                "I could not find any relevant "
                "code excerpts in the indexed "
                "project to answer this question."
            ),
            "mocked": False,
            "sources": [],
        }

    # 3. Group chunks by file.
    sources_by_file: dict[str, list[str]] = {}

    for match in matches:
        file_path = (
            match.get("metadata", {})
            .get("file_path", "Unknown file")
        )

        snippet = match.get("text", "")[:500]

        sources_by_file.setdefault(
            file_path, []
        ).append(snippet)

    sources = [
        {
            "file": file_path,
            "snippets": snippets
        }
        for file_path, snippets
        in sources_by_file.items()
    ]

    # 4. Prepare the complete context for the LLM.
    context_blocks = [
        (
            f"\n--- File: "
            f"{match.get('metadata', {}).get('file_path', 'Unknown file')} ---\n\n"
            f"{match.get('text', '')}\n"
        )
        for match in matches
    ]

    context = "\n".join(context_blocks)

    user_prompt = f"""
Here are the project excerpts retrieved
by the RAG system:

{context}

Developer's question:

{question}

Answer the question using only
the provided excerpts.

Respond in the same language as the question.

Mention the relevant files whenever appropriate.
"""

    # 5. Send the context and question to IBM Bob 2.0.
    result = call_llm(
        SYSTEM_PROMPT,
        user_prompt
    )

    # 6. Simulation mode.
    if result["mocked"]:
        return {
            "answer": (
                f"Simulation mode: "
                f"{len(sources)} source file(s) "
                "were found for your question. "
                "The relevant excerpts are displayed "
                "below, grouped by file. "
                "A complete AI-generated answer "
                "will be available once IBM Bob 2.0 "
                "is connected."
            ),
            "mocked": True,
            "sources": sources,
        }

    # 7. Return the actual LLM response.
    return {
        "answer": result["content"],
        "mocked": False,
        "sources": sources
    }