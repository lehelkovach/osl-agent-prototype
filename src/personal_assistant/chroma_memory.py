import json
import os
from typing import List, Dict, Any, Optional, Union

import chromadb

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


class ChromaMemoryTools(MemoryTools):
    """
    ChromaDB-backed MemoryTools implementation.

    Stores Nodes/Edges in a persistent collection (.chroma by default), using the
    provided embeddings (or zero-filled fallback) for semantic search.
    """

    def __init__(
        self,
        path: str = ".chroma",
        collection_name: str = "memory",
        embedding_dim: int = 3072,
    ):
        os.makedirs(path, exist_ok=True)
        self.embedding_dim = embedding_dim
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            collection_name, metadata={"hnsw:space": "cosine"}
        )

    def search(
        self,
        query_text: str,
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Queries Chroma by embedding (preferred) or text, returning stored items as dicts."""
        kwargs: Dict[str, Any] = {"n_results": top_k}
        if filters:
            kwargs["where"] = filters

        if query_embedding:
            kwargs["query_embeddings"] = [
                self._normalize_embedding(query_embedding, allow_resize=True)
            ]
        else:
            kwargs["query_texts"] = [query_text]

        results = self.collection.query(**kwargs)
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        items: List[Dict[str, Any]] = []
        for doc, meta in zip(docs, metadatas):
            try:
                item_dict = json.loads(doc)
                # merge back any metadata that may have been updated
                item_dict["metadata"] = meta
                items.append(item_dict)
            except Exception:
                continue
        return items

    def upsert(
        self,
        item: Union[Node, Edge],
        provenance: Provenance,
        embedding_request: Optional[bool] = False,
    ) -> Dict[str, Any]:
        """Persists the item into Chroma."""
        payload = item.__dict__.copy()
        labels = payload.get("labels")
        if isinstance(labels, list):
            labels_meta = ",".join(labels)
        elif labels is None:
            labels_meta = None
        else:
            labels_meta = str(labels)

        meta = {
            "kind": str(payload.get("kind")),
            "labels": labels_meta,
            "provenance_source": provenance.source,
            "provenance_trace_id": provenance.trace_id,
        }
        embedding = payload.get("llm_embedding") or []
        emb = self._normalize_embedding(embedding, allow_resize=True)

        self.collection.upsert(
            ids=[payload.get("uuid")],
            embeddings=[emb],
            documents=[json.dumps(payload)],
            metadatas=[meta],
        )
        return {"status": "success", "uuid": payload.get("uuid")}

    def _normalize_embedding(
        self, embedding: List[float], allow_resize: bool = False
    ) -> List[float]:
        """
        Ensures embedding matches expected dimension.
        Pads/truncates if allow_resize, otherwise returns zero vector.
        """
        if not embedding:
            return [0.0] * self.embedding_dim
        if len(embedding) == self.embedding_dim:
            return embedding
        if allow_resize:
            if len(embedding) > self.embedding_dim:
                return embedding[: self.embedding_dim]
            padded = embedding + [0.0] * (self.embedding_dim - len(embedding))
            return padded
        return [0.0] * self.embedding_dim
