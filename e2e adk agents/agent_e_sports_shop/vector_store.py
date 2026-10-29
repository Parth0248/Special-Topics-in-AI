"""Vector store module for Agent E: E-Commerce Sports Shop.

Provides 768-dimensional vector embedding generation, serialization,
cosine distance, cosine similarity calculation, and top-k ranking.
Supports live Google GenAI text-embedding-004 when credentials are present,
with seamless fallback to a deterministic semantic vector embedding engine.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger("agent_e.vector_store")

EMBEDDING_DIM = 768


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Computes cosine similarity between two vectors.
    
    Returns a float in [-1.0, 1.0], where 1.0 indicates identical direction.
    """
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def cosine_distance(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Computes cosine distance (1.0 - cosine_similarity).
    
    Used by pgvector's <=> operator. Lower values indicate closer proximity.
    """
    return 1.0 - cosine_similarity(vec_a, vec_b)


def serialize_vector(vec: np.ndarray) -> bytes:
    """Serializes a NumPy vector to raw float32 bytes for SQLite BLOB storage."""
    arr = np.asarray(vec, dtype=np.float32)
    return arr.tobytes()


def deserialize_vector(data: bytes, dim: int = EMBEDDING_DIM) -> np.ndarray:
    """Deserializes raw float32 bytes back into a NumPy array."""
    arr = np.frombuffer(data, dtype=np.float32)
    if arr.shape[0] != dim:
        # If length doesn't match expected dim, pad or truncate cleanly
        result = np.zeros(dim, dtype=np.float32)
        take = min(dim, arr.shape[0])
        result[:take] = arr[:take]
        return result
    return arr.copy()


class VectorStore:
    """Manages vector operations, embedding generation, and similarity ranking."""

    # Semantic concept anchors mapped to orthogonal subspaces in 768-d
    SEMANTIC_CLUSTERS = {
        "running": [
            "run", "running", "runner", "shoe", "shoes", "trail", "trailblazer",
            "marathon", "road", "pace", "stride", "cushion", "cushioning",
            "singlet", "jogging", "sprint", "lightweight", "breathable", "vibram",
            "gore-tex", "carbon", "plate", "hydration", "vest", "footwear"
        ],
        "basketball": [
            "basketball", "hoops", "court", "high-top", "high-tops", "traction",
            "zoom", "bounce", "ankle", "support", "rebound", "dunk", "slam",
            "insole", "shorts", "mesh", "leather", "composite", "knee", "pads"
        ],
        "outdoor": [
            "outdoor", "hiking", "hike", "trail", "mountain", "alpine", "rain",
            "jacket", "waterproof", "weatherproof", "shell", "merino", "wool",
            "baselayer", "backpack", "trekking", "poles", "expedition", "summit",
            "stormshield", "nomad", "thermal"
        ],
        "equipment": [
            "equipment", "fitness", "training", "workout", "gym", "weights",
            "dumbbell", "hex", "rubber", "recovery", "foam", "roller", "massage",
            "jump", "rope", "speed", "cable", "resistance", "bands", "tubes"
        ]
    }

    def __init__(
        self,
        embedding_model: str = "text-embedding-004",
        api_key: Optional[str] = None,
        dimension: int = EMBEDDING_DIM
    ) -> None:
        self.embedding_model = embedding_model
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.dimension = dimension
        self._genai_client: Optional[Any] = None
        self._init_client()

    def _init_client(self) -> None:
        """Attempts to initialize google-genai client if API key is present."""
        if not self.api_key:
            logger.info("No GOOGLE_API_KEY set; using deterministic semantic vector engine.")
            return

        try:
            from google import genai
            self._genai_client = genai.Client(api_key=self.api_key)
            logger.info("Initialized Google GenAI client for vector embeddings.")
        except Exception as e:
            logger.warning("Failed to initialize Google GenAI client (%s); using fallback.", e)
            self._genai_client = None

    def generate_embedding(self, text: str) -> np.ndarray:
        """Generates a 768-d unit vector for the given text.
        
        Attempts live Google GenAI embedding if available, otherwise generates
        a deterministic semantic embedding reflecting term semantics.
        """
        if not text or not text.strip():
            # Return zero vector if empty
            return np.zeros(self.dimension, dtype=np.float32)

        # 1. Attempt live Google GenAI text-embedding-004
        if self._genai_client is not None:
            try:
                response = self._genai_client.models.embed_content(
                    model=self.embedding_model,
                    contents=text
                )
                if response and hasattr(response, "embeddings") and response.embeddings:
                    values = response.embeddings[0].values
                    vec = np.asarray(values, dtype=np.float32)
                    if vec.shape[0] == self.dimension:
                        # Normalize to unit length
                        norm = np.linalg.norm(vec)
                        return vec / norm if norm > 0 else vec
            except Exception as exc:
                logger.debug("Live embedding failed (%s), falling back to semantic engine.", exc)

        # 2. Deterministic Semantic Embedding Engine (100% offline & reproducible)
        return self._deterministic_semantic_embedding(text)

    def _deterministic_semantic_embedding(self, text: str) -> np.ndarray:
        """Synthesizes a 768-dimensional normalized semantic vector.
        
        Maps words to deterministic pseudo-random orthogonal projections,
        blending semantic cluster subspaces so that semantically related concepts
        (e.g., 'trail running shoes' and 'Apex Trailblazer GTX') naturally have
        high cosine similarity.
        """
        tokens = re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())
        if not tokens:
            return np.zeros(self.dimension, dtype=np.float32)

        composite = np.zeros(self.dimension, dtype=np.float32)

        # Assign reserved slices of the 768 dimensions to high-level categories
        category_slices = {
            "running": (0, 192),
            "basketball": (192, 384),
            "outdoor": (384, 576),
            "equipment": (576, 768),
        }

        for token in tokens:
            # Deterministic word hash seed
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(h)
            word_vec = rng.normal(loc=0.0, scale=0.1, size=self.dimension).astype(np.float32)

            # Boost cluster category weights if token matches semantic clusters
            for cat_name, keywords in self.SEMANTIC_CLUSTERS.items():
                if token in keywords:
                    start, end = category_slices[cat_name]
                    # Concentrate energy in the category subspace
                    cat_h = int(hashlib.md5(f"{cat_name}_{token}".encode("utf-8")).hexdigest()[:8], 16)
                    cat_rng = np.random.default_rng(cat_h)
                    subspace_vec = cat_rng.normal(loc=0.5, scale=0.15, size=end - start).astype(np.float32)
                    word_vec[start:end] += subspace_vec * 2.5

            composite += word_vec

        # Normalize to unit vector (L2 norm = 1.0)
        norm = np.linalg.norm(composite)
        if norm > 0:
            composite = composite / norm
        return composite.astype(np.float32)

    def rank_similar(
        self,
        query_vector: np.ndarray,
        candidate_vectors: Sequence[np.ndarray],
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """Ranks candidate vectors by cosine similarity to query_vector.
        
        Returns:
            List of (candidate_index, similarity_score) sorted descending by score.
        """
        if not candidate_vectors:
            return []

        scores: List[Tuple[int, float]] = []
        q = np.asarray(query_vector, dtype=np.float32)

        for idx, cand in enumerate(candidate_vectors):
            sim = cosine_similarity(q, cand)
            scores.append((idx, sim))

        scores.sort(key=lambda item: item[1], reverse=True)
        return scores[:top_k]
