"""
KnowShowGo Service - FastAPI application for fuzzy ontology knowledge graph.

This service exposes the KnowShowGo API over HTTP, allowing the agent to
use it as a remote service rather than an embedded library.
"""
import os
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    ConceptCreate, ConceptResponse, SearchRequest, SearchResponse, SearchResult,
    PatternStoreRequest, PatternMatchRequest, PatternMatchResult,
    UpsertRequest, HealthResponse, Provenance
)

# Version
VERSION = "0.1.0"

app = FastAPI(
    title="KnowShowGo Service",
    description="Fuzzy Ontology Knowledge Graph as a Service",
    version=VERSION
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InMemoryStore:
    """In-memory storage for KnowShowGo concepts and edges."""
    
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, Dict[str, Any]] = {}
        self._init_prototypes()
    
    def _init_prototypes(self):
        """Initialize standard prototypes."""
        prototypes = [
            {"uuid": "proto-concept", "kind": "Prototype", "props": {"name": "Concept", "isPrototype": True}},
            {"uuid": "proto-procedure", "kind": "Prototype", "props": {"name": "Procedure", "isPrototype": True}},
            {"uuid": "proto-credential", "kind": "Prototype", "props": {"name": "Credential", "isPrototype": True}},
            {"uuid": "proto-form-pattern", "kind": "Prototype", "props": {"name": "FormPattern", "isPrototype": True}},
            {"uuid": "proto-queue-item", "kind": "Prototype", "props": {"name": "QueueItem", "isPrototype": True}},
        ]
        for p in prototypes:
            self.nodes[p["uuid"]] = {**p, "labels": [p["props"]["name"]], "embedding": []}
    
    def upsert_node(self, node: Dict[str, Any]) -> str:
        """Upsert a node."""
        node_uuid = node.get("uuid") or str(uuid.uuid4())
        self.nodes[node_uuid] = {
            "uuid": node_uuid,
            "kind": node.get("kind", "Concept"),
            "props": node.get("props", {}),
            "labels": node.get("labels", []),
            "embedding": node.get("embedding", []),
        }
        return node_uuid
    
    def upsert_edge(self, edge: Dict[str, Any]) -> str:
        """Upsert an edge."""
        edge_uuid = edge.get("uuid") or str(uuid.uuid4())
        self.edges[edge_uuid] = {
            "uuid": edge_uuid,
            "from_node": edge.get("from_node"),
            "to_node": edge.get("to_node"),
            "rel": edge.get("rel"),
            "props": edge.get("props", {}),
        }
        return edge_uuid
    
    def get_node(self, node_uuid: str) -> Optional[Dict[str, Any]]:
        """Get a node by UUID."""
        return self.nodes.get(node_uuid)
    
    def search(
        self,
        query: str,
        embedding: Optional[List[float]] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Search for nodes by query or embedding."""
        results = []
        query_lower = query.lower()
        
        for node_uuid, node in self.nodes.items():
            # Skip prototypes in search
            if node.get("props", {}).get("isPrototype"):
                continue
            
            # Calculate score
            score = 0.0
            
            # Text matching
            node_text = " ".join([
                str(node.get("kind", "")),
                " ".join(node.get("labels", [])),
                str(node.get("props", {}).get("name", "")),
                str(node.get("props", {}).get("title", "")),
                str(node.get("props", {}).get("label", "")),
            ]).lower()
            
            if query_lower in node_text:
                score = 0.8
            elif any(word in node_text for word in query_lower.split()):
                score = 0.5
            
            # Embedding similarity (if both have embeddings)
            if embedding and node.get("embedding"):
                try:
                    emb_score = self._cosine_similarity(embedding, node["embedding"])
                    score = max(score, emb_score)
                except Exception:
                    pass
            
            # Apply filters
            if filters:
                kind_filter = filters.get("kind")
                if kind_filter and node.get("kind") != kind_filter:
                    continue
            
            if score >= min_similarity:
                results.append({**node, "score": score})
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b) or len(a) == 0:
            return 0.0
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)


# Global store instance
store = InMemoryStore()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version=VERSION,
        concepts_count=len(store.nodes),
        edges_count=len(store.edges)
    )


@app.post("/concepts", response_model=ConceptResponse)
def create_concept(request: ConceptCreate):
    """Create a new concept from a prototype."""
    # Verify prototype exists
    prototype = store.get_node(request.prototype_uuid)
    if not prototype:
        raise HTTPException(status_code=404, detail=f"Prototype {request.prototype_uuid} not found")
    
    # Create concept
    concept_uuid = str(uuid.uuid4())
    concept = {
        "uuid": concept_uuid,
        "kind": "Concept",
        "props": {
            **request.json_obj,
            "prototype_uuid": request.prototype_uuid,
            "isPrototype": False,
        },
        "labels": [request.json_obj.get("name", "concept")],
        "embedding": request.embedding,
    }
    
    if request.previous_version_uuid:
        concept["props"]["previous_version_uuid"] = request.previous_version_uuid
    
    store.upsert_node(concept)
    
    # Create inherits_from edge
    store.upsert_edge({
        "from_node": concept_uuid,
        "to_node": request.prototype_uuid,
        "rel": "inherits_from",
        "props": {"created_at": datetime.now(timezone.utc).isoformat()}
    })
    
    return ConceptResponse(
        uuid=concept_uuid,
        kind="Concept",
        props=concept["props"],
        labels=concept["labels"],
        embedding=concept["embedding"]
    )


@app.get("/concepts/{concept_uuid}", response_model=ConceptResponse)
def get_concept(concept_uuid: str):
    """Get a concept by UUID."""
    concept = store.get_node(concept_uuid)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept {concept_uuid} not found")
    
    return ConceptResponse(
        uuid=concept["uuid"],
        kind=concept["kind"],
        props=concept["props"],
        labels=concept["labels"],
        embedding=concept.get("embedding")
    )


@app.post("/search", response_model=SearchResponse)
def search_concepts(request: SearchRequest):
    """Search for concepts."""
    results = store.search(
        query=request.query,
        embedding=request.embedding,
        top_k=request.top_k,
        filters=request.filters,
        min_similarity=request.min_similarity
    )
    
    return SearchResponse(
        results=[
            SearchResult(
                uuid=r["uuid"],
                kind=r["kind"],
                props=r["props"],
                score=r["score"],
                labels=r.get("labels", [])
            )
            for r in results
        ],
        total=len(results),
        query=request.query
    )


@app.post("/upsert")
def upsert(request: UpsertRequest):
    """Upsert a node or edge."""
    if request.from_node and request.to_node and request.rel:
        # It's an edge
        edge_uuid = store.upsert_edge({
            "uuid": request.uuid,
            "from_node": request.from_node,
            "to_node": request.to_node,
            "rel": request.rel,
            "props": request.props,
        })
        return {"status": "success", "uuid": edge_uuid, "type": "edge"}
    else:
        # It's a node
        node_uuid = store.upsert_node({
            "uuid": request.uuid,
            "kind": request.kind,
            "labels": request.labels,
            "props": request.props,
            "embedding": request.embedding or [],
        })
        return {"status": "success", "uuid": node_uuid, "type": "node"}


@app.post("/patterns/store")
def store_pattern(request: PatternStoreRequest):
    """Store a form pattern for reuse."""
    pattern_uuid = request.concept_uuid or str(uuid.uuid4())
    
    pattern = {
        "uuid": pattern_uuid,
        "kind": "FormPattern",
        "props": {
            "name": request.pattern_name,
            "pattern_data": request.pattern_data,
            "isPrototype": False,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        },
        "labels": ["FormPattern", request.pattern_name],
        "embedding": request.embedding,
    }
    
    store.upsert_node(pattern)
    
    # Link to prototype
    store.upsert_edge({
        "from_node": pattern_uuid,
        "to_node": "proto-form-pattern",
        "rel": "inherits_from",
        "props": {}
    })
    
    return {"status": "success", "uuid": pattern_uuid}


@app.post("/patterns/match", response_model=List[PatternMatchResult])
def match_patterns(request: PatternMatchRequest):
    """Find matching patterns for a URL/form."""
    results = store.search(
        query=f"form pattern {request.url} {request.form_type or ''}",
        top_k=request.top_k,
        filters={"kind": "FormPattern"}
    )
    
    matches = []
    for r in results:
        pattern_data = r.get("props", {}).get("pattern_data", {})
        matches.append(PatternMatchResult(
            concept={"uuid": r["uuid"], "props": r["props"]},
            pattern_data=pattern_data,
            score=r["score"]
        ))
    
    return matches


@app.get("/prototypes")
def list_prototypes():
    """List all prototypes."""
    prototypes = [
        node for node in store.nodes.values()
        if node.get("props", {}).get("isPrototype")
    ]
    return {"prototypes": prototypes}


def run_service(host: str = "0.0.0.0", port: int = 8001):
    """Run the KnowShowGo service."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_service()
