"""
Agent 1 : Indexing & Parsing Agent
------------------------------------
Ce module s'occupe de :
1. Extraire un projet .zip
2. Parcourir l'arborescence des fichiers (Folder Tree)
3. Découper (chunker) le contenu de chaque fichier en morceaux exploitables par le RAG
"""

import os
import zipfile
import tempfile
from pathlib import Path

# Extensions de fichiers qu'on considère comme "code source" à indexer.
# On ignore le reste (images, binaires, etc.) pour ne pas polluer le RAG.
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb",
    ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".html", ".css",
    ".json", ".yaml", ".yml", ".md", ".sql",
}

# Dossiers qu'on n'indexe jamais (dépendances, environnements virtuels, etc.)
IGNORED_DIRS = {
    "node_modules", "venv", ".venv", "__pycache__", ".git",
    "dist", "build", ".idea", ".vscode",
}


def extract_zip(zip_path: str) -> str:
    """
    Étape 1 : décompresse le zip du projet dans un dossier temporaire
    et retourne le chemin vers ce dossier.
    """
    extract_dir = tempfile.mkdtemp(prefix="codebase_")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    return extract_dir


def build_folder_tree(root_path: str) -> str:
    """
    Étape 2 : construit une représentation texte de l'arborescence du projet.
    Utile pour donner du contexte global à l'Agent 2 (Architecture Summarizer).
    """
    lines = []
    root = Path(root_path)

    for path in sorted(root.rglob("*")):
        # On ignore les dossiers techniques
        if any(part in IGNORED_DIRS for part in path.parts):
            continue

        depth = len(path.relative_to(root).parts) - 1
        indent = "    " * depth
        lines.append(f"{indent}{path.name}")

    return "\n".join(lines)


def collect_source_files(root_path: str) -> list[str]:
    """
    Étape 3 : liste tous les fichiers de code source à indexer,
    en excluant les dossiers ignorés et les extensions non pertinentes.
    """
    root = Path(root_path)
    files = []

    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in CODE_EXTENSIONS:
            continue
        files.append(str(path))

    return files


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    """
    Étape 4 : découpe un texte en chunks de taille fixe avec un overlap.

    Pourquoi un overlap ? Pour ne pas couper une fonction ou un bloc de code
    en plein milieu et perdre le contexte entre deux chunks consécutifs.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap  # on recule un peu pour créer le chevauchement

    return chunks


def build_chunks(root_path: str) -> list[dict]:
    """
    Étape 5 : orchestre tout le pipeline de parsing.
    Retourne une liste de chunks, chacun avec ses métadonnées
    (fichier d'origine, numéro de chunk) prêts à être envoyés au RAG.
    """
    all_chunks = []
    source_files = collect_source_files(root_path)

    for file_path in source_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue  # fichier illisible, on passe

        relative_path = os.path.relpath(file_path, root_path)
        text_chunks = chunk_text(content)

        for i, chunk in enumerate(text_chunks):
            all_chunks.append({
                "id": f"{relative_path}::{i}",
                "text": chunk,
                "metadata": {
                    "file_path": relative_path,
                    "chunk_index": i,
                },
            })

    return all_chunks
