"""
Point d'entrée FastAPI — Type 1 (Codebase Onboarding) + Type 2 (PR Reviewer)

Endpoints Type 1 :
- POST /index                : upload d'un zip -> extraction + chunking + indexation RAG (Agent 1)
- GET  /health                : vérifie que le serveur tourne
- GET  /tree/{project}        : retourne l'arborescence du dernier projet indexé
- POST /architecture/{id}     : résumé architectural (Agent 2)
- POST /ask/{id}              : Q&A sur le codebase (Agent 3)

Endpoints Type 2 :
- POST /api/v1/review          : audit sécurité/qualité (Agent 4)
- POST /api/v1/refactor        : refactoring du code (Agent 5)
- POST /api/v1/generate-tests  : génération de tests PyTest (Agent 6)
"""

import os
import shutil
from typing import Any
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.Agent1.parsing import extract_zip, build_folder_tree, build_chunks
from backend.Agent1.rag import index_chunks
from backend.Agent2.state import FOLDER_TREES
from backend.Agent2.archi_agent import summarize_architecture
from backend.Agent3.qa_agent import answer_question
from backend.Agent4.security_quality_agent import security_quality_agent
from backend.Agent5.refactoring_agent import refactor_code

app = FastAPI(title="Codebase Indexing Agent")

# Autorise Streamlit (généralement sur localhost:8501) à appeler ce backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/index")
async def index_project(file: UploadFile = File(...)):
    """
    Étape complète :
    1. Sauvegarde le zip uploadé sur disque
    2. L'extrait dans un dossier temporaire
    3. Construit l'arborescence + les chunks
    4. Indexe les chunks dans ChromaDB
    5. Retourne un résumé au frontend Streamlit
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Merci d'uploader un fichier .zip")

    project_id = str(uuid.uuid4())[:8]
    temp_zip_path = f"./_upload_{project_id}.zip"

    # 1. Sauvegarde du zip reçu
    with open(temp_zip_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # 2. Extraction
        extracted_path = extract_zip(temp_zip_path)

        # 3. Arborescence + chunking
        tree = build_folder_tree(extracted_path)
        chunks = build_chunks(extracted_path)

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Aucun fichier de code source trouvé dans le zip.",
            )

        # 4. Indexation dans le RAG
        nb_indexed = index_chunks(project_id, chunks)

        FOLDER_TREES[project_id] = tree

        # 5. Réponse pour Streamlit
        return {
            "project_id": project_id,
            "nb_files_indexed": len({c["metadata"]["file_path"] for c in chunks}),
            "nb_chunks_indexed": nb_indexed,
            "folder_tree": tree,
        }

    finally:
        # Nettoyage du zip temporaire
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)


@app.get("/tree/{project_id}")
def get_tree(project_id: str):
    tree = FOLDER_TREES.get(project_id)
    if tree is None:
        raise HTTPException(status_code=404, detail="Projet inconnu")
    return {"project_id": project_id, "folder_tree": tree}


@app.post("/architecture/{project_id}")
def get_architecture_summary(project_id: str):
    """
    Agent 2 : Architecture Summarizer Agent.
    Doit être appelé APRÈS /index — il s'appuie sur le RAG déjà construit
    par l'Agent 1 pour ce project_id.
    """
    tree = FOLDER_TREES.get(project_id)
    if tree is None:
        raise HTTPException(
            status_code=404,
            detail="Projet inconnu — indexe-le d'abord via POST /index.",
        )

    try:
        result = summarize_architecture(project_id, tree)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur lors de l'appel au LLM : {e}")

    return {
        "project_id": project_id,
        "architecture_summary": result["content"],
        "mocked": result["mocked"],
    }


class AskRequest(BaseModel):
    question: str


@app.post("/ask/{project_id}")
def ask_question(project_id: str, payload: AskRequest):
    """
    Agent 3 : Codebase Q&A Copilot Agent.
    Doit être appelé APRÈS /index — utilise le RAG construit par l'Agent 1
    pour répondre à une question sur le codebase indexé.
    """
    tree = FOLDER_TREES.get(project_id)
    if tree is None:
        raise HTTPException(
            status_code=404,
            detail="Projet inconnu — indexe-le d'abord via POST /index.",
        )

    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide.")

    try:
     result = answer_question(
      project_id,
        payload.question,
      folder_tree=tree
     )    
    except RuntimeError as e:
        # Cas où LLM_API_KEY n'est pas configurée dans .env
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur lors de l'appel au LLM : {e}")

    return {
        "project_id": project_id,
        "answer": result["answer"],
        "mocked": result["mocked"],
        "sources": result.get("sources", []),
    }


# ─────────────────────────────────────────────────────────────
# TYPE 2 : Multi-Agent PR Reviewer & Automated Tester
# ─────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    code: str
    language: str = "python"


class RefactorRequest(BaseModel):
    code: str
    findings: list[dict] = []


class GenerateTestsRequest(BaseModel):
    code: str


@app.post("/api/v1/review")
def review_code(payload: ReviewRequest):
    """
    Agent 4 : Security & Quality Agent.
    Pas de LLM ici — analyse par règles (regex + AST), donc pas de risque
    de 502 même sans LLM_API_URL configuré.
    """
    try:
        report = security_quality_agent.review(payload.code, payload.language)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return report


@app.post("/api/v1/refactor")
def refactor_code_endpoint(payload: RefactorRequest):
    """
    Agent 5 : IBM Bob Refactoring Agent.
    À appeler avec le code original + les "findings" retournés par /api/v1/review.
    """
    try:
        result = refactor_code(payload.code, payload.findings)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result


@app.post("/api/v1/generate-tests")
def generate_tests_endpoint(payload: GenerateTestsRequest):
    """
    Agent 6 : Automated Test Generator & Validator Agent.
    À appeler avec le code refactorisé retourné par /api/v1/refactor.

    Retourne :
      - filename        : nom suggéré pour le fichier de tests (str)
      - test_code       : code Python complet du fichier de tests (str)
      - test_count      : nombre de fonctions test_* (int)
      - explanation     : stratégie de tests ou message de simulation (str)
      - generation_mode : "llm" | "simulation" | "error" (str)
      - mocked          : True si mode simulation (bool)
      - syntax_ok       : syntaxe du code refactorisé valide (bool)
      - syntax_errors   : liste des erreurs de syntaxe (list)
      - pytest_result   : résultat complet de pytest (passed, stdout, summary…)

    En cas d'erreur de configuration LLM (clé manquante, URL invalide,
    réponse HTTP 4xx/5xx), retourne HTTP 502 avec un message explicite.
    """
   