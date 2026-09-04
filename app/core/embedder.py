# app/core/embedder.py
# embedder = retrieval layer
# Switched from Ollama HTTP API to sentence-transformers for self-contained deployment.
# Model: BAAI/bge-base-en-v1.5 — 768-dim, strong retrieval quality, no external service required.
# Re-run scripts/embed_resume.py and scripts/build_taxonomy_embeddings.py
# after any change to the model to keep all .npy files consistent.

from sentence_transformers import SentenceTransformer

_model = None

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-base-en-v1.5", local_files_only=True)
    return _model


def embed_text(text: str) -> list:
    return _get_model().encode(text, convert_to_numpy=True).tolist()
