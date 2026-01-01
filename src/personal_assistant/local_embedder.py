import hashlib
import os
from typing import List


class LocalEmbedder:
    """
    Lightweight embedding helper. If sentence-transformers is installed, uses it.
    Otherwise falls back to a deterministic hash-based vector (fast, no deps).
    """

    def __init__(self, model_name: str = None, dim: int | None = 16):
        """
        If an explicit dim other than the default is provided, prefer the hash fallback
        even if sentence-transformers is installed. The model path can still be forced
        via `model_name` or LOCAL_EMBED_MODEL.
        """
        default_dim = 16
        explicit_dim = dim is not None and dim != default_dim
        self.dim = dim if dim is not None else default_dim
        self.model = None

        model_name = model_name or os.getenv("LOCAL_EMBED_MODEL")
        # If the caller asked for a specific dim, interpret that as opting into the
        # lightweight hash mode unless a model is explicitly requested.
        if explicit_dim and not model_name:
            return

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            if model_name:
                self.model = SentenceTransformer(model_name)
            else:
                self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            self.dim = len(self.model.encode("test"))
        except Exception:
            self.model = None
        if self.model is None and (model_name or explicit_dim):
            # adjust dim if explicitly provided
            try:
                d = int(os.getenv("LOCAL_EMBED_DIM", self.dim))
                self.dim = d
            except Exception:
                pass

    def embed(self, text: str) -> List[float]:
        if self.model:
            return self.model.encode(text).tolist()
        # hash-based fallback
        h = hashlib.sha256(text.encode()).digest()
        # produce dim floats in [-1,1]
        vals = []
        for i in range(self.dim):
            b = h[i % len(h)]
            vals.append(((b / 255.0) * 2) - 1)
        return vals
