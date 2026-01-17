# KnowShowGo Service Handoff Document

**Date**: 2026-01-17  
**From**: OSL Agent Prototype  
**To**: KnowShowGo Separate Repository  
**Version**: 0.2.0

> **Latest Update**: Added Pattern Evolution (transfer/generalize), Centroid-Based Embedding Evolution, and First-Class Edges (relationships as searchable nodes).

---

## Executive Summary

The OSL Agent Prototype has developed a **KnowShowGo HTTP Service** that exposes the fuzzy ontology knowledge graph as a standalone FastAPI service. This allows the KnowShowGo functionality to be:

1. Run as a separate microservice
2. Shared across multiple agents/applications
3. Scaled independently
4. Developed and tested in isolation

This document provides the specifications and code for updating the separate KnowShowGo repository.

---

## New Components to Add

### 1. Service Directory Structure

```
knowshowgo/
├── service/
│   ├── __init__.py
│   ├── models.py      # Pydantic models for API
│   ├── service.py     # FastAPI application
│   ├── client.py      # HTTP client + mock client
│   └── tests/
│       ├── __init__.py
│       ├── test_service.py
│       └── test_client.py
├── scripts/
│   └── start_service.sh
└── ...existing files...
```

### 2. API Endpoints

The service exposes these HTTP endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check with version and stats |
| POST | `/concepts` | Create concept from prototype |
| GET | `/concepts/{uuid}` | Get concept by UUID |
| POST | `/search` | Semantic search for concepts |
| POST | `/upsert` | Upsert node or edge |
| POST | `/patterns/store` | Store form pattern |
| POST | `/patterns/match` | Find matching patterns |
| GET | `/prototypes` | List all prototypes |

### 3. Pydantic Models (`models.py`)

```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Provenance(BaseModel):
    source: str = "api"
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    confidence: float = 1.0
    trace_id: str = "ksg-api"


class ConceptCreate(BaseModel):
    prototype_uuid: str
    json_obj: Dict[str, Any]
    embedding: List[float] = Field(default_factory=list)
    previous_version_uuid: Optional[str] = None


class ConceptResponse(BaseModel):
    uuid: str
    kind: str
    props: Dict[str, Any]
    labels: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = None


class SearchRequest(BaseModel):
    query: str
    embedding: Optional[List[float]] = None
    top_k: int = 10
    filters: Optional[Dict[str, Any]] = None
    min_similarity: float = 0.0


class SearchResult(BaseModel):
    uuid: str
    kind: str
    props: Dict[str, Any]
    score: float
    labels: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    query: str


class PatternStoreRequest(BaseModel):
    pattern_name: str
    pattern_data: Dict[str, Any]
    embedding: List[float] = Field(default_factory=list)
    concept_uuid: Optional[str] = None


class PatternMatchRequest(BaseModel):
    url: str
    html: Optional[str] = None
    form_type: Optional[str] = None
    fingerprint: Optional[Dict[str, Any]] = None
    top_k: int = 5


class PatternMatchResult(BaseModel):
    concept: Dict[str, Any]
    pattern_data: Dict[str, Any]
    score: float


class UpsertRequest(BaseModel):
    kind: str
    uuid: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    props: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    from_node: Optional[str] = None  # For edges
    to_node: Optional[str] = None
    rel: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    concepts_count: int
    edges_count: int
```

### 4. FastAPI Service (`service.py`)

Key features:
- In-memory store (can be swapped for ArangoDB/persistent backend)
- Standard prototypes initialized on startup
- Cosine similarity for embedding search
- CORS enabled for cross-origin requests

```python
# See full implementation in:
# /workspace/services/knowshowgo/service.py

# Key endpoints:
@app.get("/health")
def health_check() -> HealthResponse

@app.post("/concepts")
def create_concept(request: ConceptCreate) -> ConceptResponse

@app.get("/concepts/{concept_uuid}")
def get_concept(concept_uuid: str) -> ConceptResponse

@app.post("/search")
def search_concepts(request: SearchRequest) -> SearchResponse

@app.post("/upsert")
def upsert(request: UpsertRequest) -> dict

@app.post("/patterns/store")
def store_pattern(request: PatternStoreRequest) -> dict

@app.post("/patterns/match")
def match_patterns(request: PatternMatchRequest) -> List[PatternMatchResult]

@app.get("/prototypes")
def list_prototypes() -> dict
```

### 5. HTTP Client (`client.py`)

Two client implementations:

#### KnowShowGoClient (Real HTTP Client)
```python
class KnowShowGoClient:
    def __init__(self, base_url: str = None, embed_fn = None, timeout: int = 30)
    
    def health() -> Dict
    def is_available() -> bool
    def create_concept(prototype_uuid, json_obj, embedding=None, ...) -> str
    def get_concept(concept_uuid) -> Dict
    def search(query, embedding=None, top_k=10, filters=None) -> List[Dict]
    def upsert(kind, props, uuid=None, labels=None, ...) -> str
    def store_cpms_pattern(pattern_name, pattern_data, embedding=None) -> str
    def find_best_cpms_pattern(url, html=None, form_type=None) -> List[Dict]
    def list_prototypes() -> List[Dict]
```

#### MockKnowShowGoClient (For Testing)
```python
class MockKnowShowGoClient:
    # Same interface as KnowShowGoClient
    # Stores data in-memory for testing without running service
```

### 6. Adapter for Embedded/Service Switching

```python
class KnowShowGoAdapter:
    """
    Unified interface that auto-detects service availability.
    Falls back to embedded KnowShowGoAPI if service unavailable.
    """
    
    @classmethod
    def create(cls, memory=None, embed_fn=None, force_embedded=False, force_service=False):
        # Checks KNOWSHOWGO_URL env var
        # Returns service client if available, else embedded API
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KNOWSHOWGO_URL` | `http://localhost:8001` | Service URL |
| `KNOWSHOWGO_PORT` | `8001` | Service port |
| `KNOWSHOWGO_HOST` | `0.0.0.0` | Service host |
| `USE_KNOWSHOWGO_SERVICE` | `false` | Force service mode |

### Startup Script

```bash
#!/bin/bash
# start_service.sh

PORT="${KNOWSHOWGO_PORT:-8001}"
HOST="${KNOWSHOWGO_HOST:-0.0.0.0}"

echo "Starting KnowShowGo service on $HOST:$PORT..."
uvicorn knowshowgo.service.service:app --host $HOST --port $PORT
```

---

## Test Coverage

### Service Tests (38 tests)
- Health endpoint
- Concept CRUD operations
- Search functionality
- Pattern storage and matching
- Prototype listing

### Client Tests (24 tests)
- Mock client operations
- Real client with mocked HTTP
- Connection error handling
- Embedding generation

### Integration Tests (10 tests)
- Create and retrieve concepts
- Pattern storage and retrieval
- Search filtering
- Service availability detection

---

## Migration Notes

### From Embedded to Service

1. **No code changes required** if using `KnowShowGoAdapter`
2. Set `KNOWSHOWGO_URL` environment variable
3. Start the service: `./scripts/start_service.sh`
4. Adapter auto-detects and switches to service mode

### Backward Compatibility

- All existing `KnowShowGoAPI` methods are available via client
- Same interface, same return types
- Embedding functions work the same way

---

## Files to Copy

From `/workspace/services/knowshowgo/`:
- `__init__.py`
- `models.py`
- `service.py`
- `client.py`
- `tests/__init__.py`
- `tests/test_service.py`
- `tests/test_client.py`

From `/workspace/src/personal_assistant/`:
- `knowshowgo_adapter.py` (optional, for adapter pattern)

From `/workspace/scripts/`:
- `start_knowshowgo_service.sh`

---

## API Usage Examples

### Python Client
```python
from knowshowgo.service.client import KnowShowGoClient

client = KnowShowGoClient(base_url="http://localhost:8001")

# Check health
print(client.health())

# Create concept
uuid = client.create_concept(
    prototype_uuid="proto-concept",
    json_obj={"name": "MyProcedure", "steps": [...]},
    embedding=[0.1, 0.2, ...]
)

# Search
results = client.search("login procedure", top_k=5)

# Store pattern
client.store_cpms_pattern(
    pattern_name="linkedin-login",
    pattern_data={"form_type": "login", "fields": [...]}
)
```

### cURL Examples
```bash
# Health check
curl http://localhost:8001/health

# Create concept
curl -X POST http://localhost:8001/concepts \
  -H "Content-Type: application/json" \
  -d '{"prototype_uuid": "proto-concept", "json_obj": {"name": "Test"}}'

# Search
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query": "login", "top_k": 5}'
```

---

---

## NEW: Pattern Evolution Methods (v0.2.0)

These methods support the Learn → Transfer → Generalize loop:

### Pattern Evolution API

| Method | Purpose |
|--------|---------|
| `find_similar_patterns(query, top_k, min_similarity)` | Semantic search for transferable patterns |
| `transfer_pattern(source_uuid, target_context, llm_fn)` | LLM-assisted field mapping between patterns |
| `record_pattern_success(pattern_uuid, context)` | Track successful pattern applications |
| `auto_generalize(pattern_uuid, min_similar, min_similarity)` | Auto-merge similar successful patterns |
| `find_generalized_pattern(query)` | Prefer proven generalized patterns |

### Usage Example
```python
# Find similar patterns for transfer
similar = ksg.find_similar_patterns("checkout form", min_similarity=0.6)

# Transfer pattern to new context
result = ksg.transfer_pattern(
    source_pattern_uuid=similar[0]["uuid"],
    target_context={
        "url": "https://newsite.com/checkout",
        "fields": ["card_number", "expiry", "cvv"],
    },
    llm_fn=my_llm_function,  # Optional LLM for field mapping
)

# Record success and trigger auto-generalization
ksg.record_pattern_success(pattern_uuid, context={"url": "..."})
gen_result = ksg.auto_generalize(pattern_uuid, min_similar=2)
```

---

## NEW: Centroid-Based Embedding Evolution (v0.2.0)

Concepts evolve their embeddings based on exemplar centroids:

### Centroid API

| Method | Purpose |
|--------|---------|
| `add_exemplar(concept_uuid, exemplar_embedding, exemplar_uuid)` | Add exemplar, update centroid |
| `get_concept_centroid(concept_uuid)` | Get current averaged embedding |
| `recompute_centroid(concept_uuid)` | Recompute from all linked exemplars |

### How It Works
```python
# Initial concept with embedding
uuid = ksg.store_cpms_pattern("Login Pattern", {...}, embedding=[1.0, 0.0, ...])

# As exemplars are added, embedding evolves toward centroid
ksg.add_exemplar(uuid, exemplar_embedding=[0.5, 0.5, ...])
ksg.add_exemplar(uuid, exemplar_embedding=[0.3, 0.7, ...])

# Concept embedding is now average of all exemplars
# Allows concepts to "drift" toward their actual usage patterns
```

### Storage
Concepts track:
- `_embedding_sum`: Running sum for incremental updates
- `_exemplar_count`: Number of exemplars
- `llm_embedding`: Current centroid (sum / count)

---

## NEW: First-Class Edges (Relationships as Nodes) (v0.2.0)

Relationships are first-class citizens with embeddings:

### Relationship API

| Method | Purpose |
|--------|---------|
| `create_relationship(from_uuid, to_uuid, rel_type, properties, embedding)` | Create searchable relationship |
| `search_relationships(query, rel_type, top_k)` | Find relationships by similarity |

### Data Model
```
Relationship Node:
├── uuid
├── kind: "Relationship"
├── labels: ["Relationship", rel_type]
├── props:
│   ├── rel_type: "depends_on"
│   ├── from_uuid: <source>
│   ├── to_uuid: <target>
│   └── ...custom properties
└── llm_embedding: [...]  # For similarity search

Edges:
├── from_node → relationship_node (has_outgoing)
└── relationship_node → to_node (points_to)
```

### Usage
```python
# Create searchable relationship
ksg.create_relationship(
    from_uuid=login_form_uuid,
    to_uuid=auth_service_uuid,
    rel_type="requires",
    properties={"strength": 0.9},
)

# Search for similar relationships
results = ksg.search_relationships("authentication dependency")
```

---

## Helper Functions (v0.2.0)

```python
from src.personal_assistant.knowshowgo import (
    cosine_similarity,  # Compare two vectors
    vector_add,         # Element-wise addition
    vector_scale,       # Scalar multiplication
    compute_centroid,   # Average of embeddings
)
```

---

## Files to Copy (Updated)

From `/workspace/src/personal_assistant/`:
- `knowshowgo.py` - **Updated with pattern evolution, centroids, relationships**
- `knowshowgo_adapter.py`
- `form_fingerprint.py`
- `ksg_orm.py`
- `ksg.py`

From `/workspace/services/knowshowgo/`:
- `service.py`, `client.py`, `models.py`
- `tests/`

From `/workspace/tests/`:
- `test_knowshowgo_pattern_evolution.py` - **25 tests**
- `test_knowshowgo_centroid_edges.py` - **18 tests**
- `test_knowshowgo*.py` - Existing tests

---

## Test Coverage (Updated)

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_knowshowgo.py` | 2 | Core API |
| `test_knowshowgo_adapter.py` | 10 | Backend switching |
| `test_knowshowgo_associations.py` | 5 | Fuzzy edges |
| `test_knowshowgo_dag_and_recall.py` | 3 | DAG operations |
| `test_knowshowgo_generalization.py` | 5 | Concept generalization |
| `test_knowshowgo_pattern_evolution.py` | 25 | **NEW** Transfer/generalize |
| `test_knowshowgo_centroid_edges.py` | 18 | **NEW** Centroids/relationships |
| `test_knowshowgo_recursive.py` | 5 | Recursive concepts |
| `test_knowshowgo_service_integration.py` | 10 | HTTP service |

**Total: 83+ KnowShowGo tests**

---

## Next Steps for KnowShowGo Repository

1. **Add service module** with the files listed above
2. **Add persistent backend** (ArangoDB integration)
3. **Add authentication** (API keys, JWT)
4. **Add rate limiting** for production use
5. **Add Docker support** for containerized deployment
6. **Add OpenAPI docs** at `/docs` endpoint (auto-generated by FastAPI)
7. **NEW: Add pattern evolution endpoints** to HTTP service
8. **NEW: Add centroid endpoints** to HTTP service
9. **NEW: Add relationship endpoints** to HTTP service
10. **FUTURE: Graph embeddings** (hybrid, GraphSAGE, hyperbolic) - see `KNOWSHOWGO-GRAPH-EMBEDDINGS-VISION.md`

---

## Contact

For questions about this implementation, refer to:
- `/workspace/docs/session-notes.md` - Development history
- `/workspace/services/knowshowgo/` - Full source code
- `/workspace/tests/test_knowshowgo_*.py` - Test examples
