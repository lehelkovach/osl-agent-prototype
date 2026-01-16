# KnowShowGo Service Handoff Document

**Date**: 2026-01-16  
**From**: OSL Agent Prototype  
**To**: KnowShowGo Separate Repository  
**Version**: 0.1.0

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

## Next Steps for KnowShowGo Repository

1. **Add service module** with the files listed above
2. **Add persistent backend** (ArangoDB integration)
3. **Add authentication** (API keys, JWT)
4. **Add rate limiting** for production use
5. **Add Docker support** for containerized deployment
6. **Add OpenAPI docs** at `/docs` endpoint (auto-generated by FastAPI)

---

## Contact

For questions about this implementation, refer to:
- `/workspace/docs/session-notes.md` - Development history
- `/workspace/services/knowshowgo/` - Full source code
- `/workspace/tests/test_knowshowgo_*.py` - Test examples
