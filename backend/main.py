"""
Point d'entrée FastAPI — Type 1 (Codebase Onboarding) + Type 2 (PR Reviewer)

Type 1 :
- POST /index
- GET  /health
- GET  /tree/{project}
- POST /architecture/{id}
- POST /ask/{id}

Type 2 :
- POST /api/v1/review
- POST /api/v1/refactor
- POST /api/v1/generate-tests
- POST /api/v1/review-pipeline
"""

import os
import shutil
import uuid

from typing import Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.Agent1.parsing import extract_zip, build_folder_tree, build_chunks
from backend.Agent1.rag import index_chunks
from backend.Agent2.state import FOLDER_TREES
from backend.Agent2.archi_agent import summarize_architecture
from backend.Agent3.qa_agent import answer_question
from backend.Agent4.security_quality_agent import security_quality_agent
from backend.agent5.refactoring_agent import refactor_code
from backend.agent6.test_generator_agent import generate_tests


app = FastAPI(title="Codebase Indexing Agent")


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
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Merci d'uploader un fichier .zip",
        )

    project_id = str(uuid.uuid4())[:8]
    temp_zip_path = f"./_upload_{project_id}.zip"

    with open(temp_zip_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        extracted_path = extract_zip(temp_zip_path)

        tree = build_folder_tree(extracted_path)
        chunks = build_chunks(extracted_path)

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Aucun fichier de code source trouvé dans le zip.",
            )

        nb_indexed = index_chunks(project_id, chunks)

        FOLDER_TREES[project_id] = tree

        return {
            "project_id": project_id,
            "nb_files_indexed": len(
                {c["metadata"]["file_path"] for c in chunks}
            ),
            "nb_chunks_indexed": nb_indexed,
            "folder_tree": tree,
        }

    finally:
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)


@app.get("/tree/{project_id}")
def get_tree(project_id: str):
    tree = FOLDER_TREES.get(project_id)

    if tree is None:
        raise HTTPException(
            status_code=404,
            detail="Projet inconnu",
        )

    return {
        "project_id": project_id,
        "folder_tree": tree,
    }


@app.post("/architecture/{project_id}")
def get_architecture_summary(project_id: str):
    tree = FOLDER_TREES.get(project_id)

    if tree is None:
        raise HTTPException(
            status_code=404,
            detail="Projet inconnu — indexe-le d'abord via POST /index.",
        )

    try:
        result = summarize_architecture(project_id, tree)
    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur lors de l'appel au LLM : {e}",
        )

    return {
        "project_id": project_id,
        "architecture_summary": result["content"],
        "mocked": result["mocked"],
    }


class AskRequest(BaseModel):
    question: str


@app.post("/ask/{project_id}")
def ask_question(project_id: str, payload: AskRequest):
    tree = FOLDER_TREES.get(project_id)

    if tree is None:
        raise HTTPException(
            status_code=404,
            detail="Projet inconnu — indexe-le d'abord via POST /index.",
        )

    if not payload.question.strip():
        raise HTTPException(
            status_code=400,
            detail="La question ne peut pas être vide.",
        )

    try:
        result = answer_question(
            project_id,
            payload.question,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur lors de l'appel au LLM : {e}",
        )

    return {
        "project_id": project_id,
        "answer": result["answer"],
        "mocked": result["mocked"],
    }


# ============================================================
# TYPE 2 — PR REVIEWER
# ============================================================

class ReviewRequest(BaseModel):
    code: str
    language: str = "python"


class RefactorRequest(BaseModel):
    code: str
    findings: list[dict] = Field(default_factory=list)


class GenerateTestsRequest(BaseModel):
    code: str


class ReviewPipelineRequest(BaseModel):
    code: str
    language: str = "python"


@app.post("/api/v1/review")
def review_code(payload: ReviewRequest):
    """
    Agent 4 :
    Security & Quality Agent
    """

    if not payload.code.strip():
        raise HTTPException(
            status_code=400,
            detail="Le code ne peut pas être vide.",
        )

    try:
        report = security_quality_agent.review(
            payload.code,
            payload.language,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    return report


@app.post("/api/v1/refactor")
def refactor_code_endpoint(payload: RefactorRequest):
    """
    Agent 5 :
    Refactoring Agent
    """

    if not payload.code.strip():
        raise HTTPException(
            status_code=400,
            detail="Le code ne peut pas être vide.",
        )

    try:
        result = refactor_code(
            payload.code,
            payload.findings,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=502,
            detail=str(e),
        )

    return result


@app.post("/api/v1/generate-tests")
def generate_tests_endpoint(payload: GenerateTestsRequest):
    """
    Agent 6 :
    Automated Test Generator Agent
    """

    if not payload.code.strip():
        raise HTTPException(
            status_code=400,
            detail="Le code ne peut pas être vide.",
        )

    try:
        result = generate_tests(payload.code)
    except RuntimeError as e:
        raise HTTPException(
            status_code=502,
            detail=str(e),
        )

    return result


@app.post("/api/v1/review-pipeline")
def review_pipeline(payload: ReviewPipelineRequest):
    if not payload.code.strip():
        raise HTTPException(status_code=400, detail="Le code ne peut pas être vide.")

    try:
        audit: dict[str, Any] = security_quality_agent.review(
            payload.code, payload.language
        )

        refactoring = refactor_code(
            payload.code,
            audit["findings"]
        )

        tests = generate_tests(
            refactoring["refactored_code"]
        )

        return {
            "audit": audit,
            "refactoring": refactoring,
            "tests": tests,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur dans le pipeline Type 2 : {e}"
        )