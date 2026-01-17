"""Data models for KnowShowGo Service API."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Provenance(BaseModel):
    """Provenance information for tracking data origin."""
    source: str = "api"
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    confidence: float = 1.0
    trace_id: str = "ksg-api"


class ConceptCreate(BaseModel):
    """Request to create a concept."""
    prototype_uuid: str
    json_obj: Dict[str, Any]
    embedding: List[float] = Field(default_factory=list)
    previous_version_uuid: Optional[str] = None


class ConceptResponse(BaseModel):
    """Response for concept operations."""
    uuid: str
    kind: str
    props: Dict[str, Any]
    labels: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = None


class SearchRequest(BaseModel):
    """Request for semantic search."""
    query: str
    embedding: Optional[List[float]] = None
    top_k: int = 10
    filters: Optional[Dict[str, Any]] = None
    min_similarity: float = 0.0


class SearchResult(BaseModel):
    """Single search result."""
    uuid: str
    kind: str
    props: Dict[str, Any]
    score: float
    labels: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Response for search operations."""
    results: List[SearchResult]
    total: int
    query: str


class PatternStoreRequest(BaseModel):
    """Request to store a form pattern."""
    pattern_name: str
    pattern_data: Dict[str, Any]
    embedding: List[float] = Field(default_factory=list)
    concept_uuid: Optional[str] = None


class PatternMatchRequest(BaseModel):
    """Request to find matching patterns."""
    url: str
    html: Optional[str] = None
    form_type: Optional[str] = None
    fingerprint: Optional[Dict[str, Any]] = None
    top_k: int = 5


class PatternMatchResult(BaseModel):
    """Pattern match result."""
    concept: Dict[str, Any]
    pattern_data: Dict[str, Any]
    score: float


class UpsertRequest(BaseModel):
    """Request to upsert a node or edge."""
    kind: str
    uuid: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    props: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    # For edges
    from_node: Optional[str] = None
    to_node: Optional[str] = None
    rel: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    concepts_count: int
    edges_count: int
