import os
from typing import List, Dict, Any, Optional, Union
from math import sqrt

from arango import ArangoClient
from arango.database import StandardDatabase

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


class ArangoMemoryTools(MemoryTools):
    """
    ArangoDB-backed MemoryTools implementation.

    Stores Nodes in a document collection and Edges in an edge collection.
    Embeddings are stored on the node and scored client-side with cosine similarity
    (small-data friendly fallback; switch to native vector indexes if available).
    """

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        db_name: Optional[str] = None,
        nodes_collection: str = "nodes",
        edges_collection: str = "edges",
        verify: Optional[Union[str, bool]] = None,
    ):
        self.url = url or os.getenv("ARANGO_URL", "http://localhost:8529")
        self.username = username or os.getenv("ARANGO_USER", "root")
        self.password = password or os.getenv("ARANGO_PASSWORD", "")
        self.db_name = db_name or os.getenv("ARANGO_DB", "agent_memory")
        self.nodes_collection_name = nodes_collection
        self.edges_collection_name = edges_collection
        self.verify = self._resolve_verify(verify)

        self.client = ArangoClient(hosts=self.url, verify_override=self.verify)
        # Connect (create db if needed and permitted)
        sys_db = self.client.db("_system", username=self.username, password=self.password)
        if not sys_db.has_database(self.db_name):
            sys_db.create_database(self.db_name)
        self.db: StandardDatabase = self.client.db(
            self.db_name, username=self.username, password=self.password
        )
        self._ensure_collections()

    def _ensure_collections(self):
        if not self.db.has_collection(self.nodes_collection_name):
            self.db.create_collection(self.nodes_collection_name)
        if not self.db.has_collection(self.edges_collection_name):
            self.db.create_collection(self.edges_collection_name, edge=True)
        self.nodes = self.db.collection(self.nodes_collection_name)
        self.edges = self.db.collection(self.edges_collection_name)

    def search(
        self,
        query_text: str,
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Search over nodes with optional embedding and lightweight text scoring."""
        docs = []
        cursor = self.nodes.all()
        for doc in cursor:
            if filters:
                skip = False
                for k, v in filters.items():
                    if doc.get(k) != v:
                        skip = True
                        break
                if skip:
                    continue
            docs.append(doc)

        def cosine(a: List[float], b: List[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sqrt(sum(x * x for x in a))
            norm_b = sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        tokens = [t for t in query_text.lower().split() if t]

        def text_score(doc: Dict[str, Any]) -> float:
            score = 0.0
            labels = " ".join(doc.get("labels", []) or []).lower()
            props = doc.get("props", {}) or {}
            vals = []
            for v in props.values():
                if isinstance(v, str):
                    vals.append(v.lower())
                elif isinstance(v, list):
                    vals.extend([str(x).lower() for x in v if isinstance(x, (str, int, float))])
            blob = labels + " " + " ".join(vals)
            for tok in tokens:
                if tok in blob:
                    score += 1.0
            return score

        scored_docs = []
        for d in docs:
            emb_score = cosine(query_embedding, d.get("llm_embedding", []) or []) if query_embedding else 0.0
            txt_score = text_score(d)
            total = emb_score + txt_score
            scored_docs.append((total, d))

        scored_docs.sort(key=lambda t: t[0], reverse=True)
        return [d for _, d in scored_docs[:top_k]]

    def upsert(
        self,
        item: Union[Node, Edge],
        provenance: Provenance,
        embedding_request: Optional[bool] = False,
    ) -> Dict[str, Any]:
        """Upsert node/edge into Arango collections."""
        if isinstance(item, Node):
            doc = item.__dict__.copy()
            doc["_key"] = item.uuid
            doc["provenance"] = provenance.__dict__
            self.nodes.insert(doc, overwrite=True)
            return {"status": "success", "uuid": item.uuid}
        elif isinstance(item, Edge):
            edge = item.__dict__.copy()
            edge["_key"] = item.uuid
            edge["_from"] = f"{self.nodes_collection_name}/{item.from_node}"
            edge["_to"] = f"{self.nodes_collection_name}/{item.to_node}"
            edge["provenance"] = provenance.__dict__
            self.edges.insert(edge, overwrite=True)
            return {"status": "success", "uuid": item.uuid}
        return {"status": "error", "error": "unknown item type"}

    def _resolve_verify(self, verify: Optional[Union[str, bool]]) -> Union[str, bool]:
        """
        Resolve TLS verification value for ArangoClient.
        - If verify is provided, use it.
        - Otherwise read ARANGO_VERIFY:
            * "false"/"0"/"no" => False
            * path to a cert file => used as verify path
            * unset => True
        """
        if verify is not None:
            return verify
        env_val = os.getenv("ARANGO_VERIFY")
        if env_val is None:
            return True
        lowered = env_val.lower()
        if lowered in ("false", "0", "no"):
            return False
        if lowered in ("true", "1", "yes"):
            return True
        # Treat other string values as a path to a CA bundle
        return os.path.abspath(os.path.expanduser(env_val))
