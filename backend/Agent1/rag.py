"""
Agent 1 (suite) : stockage RAG avec ChromaDB
----------------------------------------------
ChromaDB gère automatiquement les embeddings avec un modèle local
(all-MiniLM-L6-v2 via sentence-transformers), donc pas besoin de clé API
pour CETTE étape. La clé secrète que tu as déjà servira plus tard pour
les Agents 2 et 3, qui eux appellent le LLM (IBM Bob 2.0).
"""

import chromadb

# Client persistant : les données sont sauvegardées sur disque
# dans le dossier "./chroma_db", donc l'index survit au redémarrage du serveur.
client = chromadb.PersistentClient(path="./chroma_db")


def get_or_create_collection(project_id: str):
    """
    Une "collection" Chroma = un index RAG isolé pour un projet donné.
    On utilise project_id pour que plusieurs projets indexés ne se mélangent pas.
    """
    return client.get_or_create_collection(name=project_id)


def index_chunks(project_id: str, chunks: list[dict]) -> int:
    """
    Envoie les chunks dans ChromaDB. Chroma calcule les embeddings
    automatiquement en arrière-plan (pas besoin de le faire à la main).
    """
    collection = get_or_create_collection(project_id)

    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    # upsert = ajoute ou met à jour si l'id existe déjà (utile si on réindexe)
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    return len(chunks)


def query_index(project_id: str, question: str, n_results: int = 5) -> list[dict]:
    """
    Sera utilisé plus tard par l'Agent 3 (Q&A Copilot) : recherche les chunks
    les plus pertinents par rapport à une question posée par le développeur.
    """
    collection = get_or_create_collection(project_id)
    results = collection.query(query_texts=[question], n_results=n_results)

    matches = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        matches.append({"text": doc, "metadata": meta, "distance": dist})

    return matches