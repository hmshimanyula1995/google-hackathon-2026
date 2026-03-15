"""Firestore vector search tool for Next '25 knowledge base.

This is the single source of truth for all knowledge retrieval.
Every factual claim Alex makes must originate from this tool.
"""

import os

import vertexai
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

COLLECTION = "session_chunks"
EMBEDDING_MODEL = "text-embedding-005"
EMBEDDING_DIMENSIONS = 768

# Module-level clients (initialized once)
_db: firestore.Client | None = None
_vertexai_initialized = False
_embedding_model: TextEmbeddingModel | None = None


def _get_db() -> firestore.Client:
    """Get or create Firestore client."""
    global _db
    if _db is None:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "next-live-agent")
        _db = firestore.Client(project=project_id)
    return _db


def _get_embedding_model() -> TextEmbeddingModel:
    """Get or create embedding model (initialized once)."""
    global _vertexai_initialized, _embedding_model
    if not _vertexai_initialized:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "next-live-agent")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        vertexai.init(project=project_id, location=location)
        _vertexai_initialized = True
    if _embedding_model is None:
        _embedding_model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    return _embedding_model


def _embed_query(query: str) -> list[float]:
    """Embed a search query using text-embedding-005."""
    model = _get_embedding_model()
    inputs = [TextEmbeddingInput(text=query, task_type="RETRIEVAL_QUERY")]
    embeddings = model.get_embeddings(
        inputs,
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )
    return embeddings[0].values


def search_next25_sessions(query: str, top_k: int = 5) -> dict:
    """Search the Next '25 knowledge base for relevant session content.

    Performs vector similarity search against the Firestore session_chunks
    collection using cosine distance. Returns the most relevant chunks
    with full metadata including session title, speakers, and YouTube URLs.

    Args:
        query: Natural language question or topic to search for.
        top_k: Number of results to return. Use 5 for general questions,
               8 for questions spanning multiple topics.

    Returns:
        A dictionary with 'status' and 'results' fields. Each result contains
        title, track, speakers, youtube_url, start_time, and raw_text content.
    """
    try:
        # Embed the query
        query_embedding = _embed_query(query)

        # Vector search in Firestore
        db = _get_db()
        collection_ref = db.collection(COLLECTION)

        vector_query = collection_ref.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_embedding),
            distance_measure=DistanceMeasure.COSINE,
            limit=top_k,
        )

        docs = list(vector_query.stream())

        if not docs:
            return {
                "status": "no_results",
                "query": query,
                "results": [],
                "message": f"No results found for query: {query}",
            }

        results = []
        for doc in docs:
            data = doc.to_dict()
            results.append({
                "title": data.get("title", "Unknown"),
                "track": data.get("track", "Unknown"),
                "speakers": data.get("speakers", []),
                "youtube_url": data.get("youtube_url", ""),
                "start_time": data.get("start_time", 0),
                "raw_text": data.get("raw_text", ""),
            })

        return {
            "status": "success",
            "query": query,
            "result_count": len(results),
            "results": results,
        }

    except Exception as e:
        return {
            "status": "error",
            "query": query,
            "results": [],
            "message": f"Search failed: {str(e)}",
        }
