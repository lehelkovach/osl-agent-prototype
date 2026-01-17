from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse
import logging
import json

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools
from src.personal_assistant.form_fingerprint import compute_form_fingerprint
from src.personal_assistant.ksg_orm import KSGORM


logger = logging.getLogger(__name__)

EmbedFn = Callable[[str], List[float]]
LLMFn = Callable[[str], str]  # Function that takes a prompt and returns LLM response


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def vector_add(a: List[float], b: List[float]) -> List[float]:
    """Add two vectors element-wise."""
    if not a:
        return b or []
    if not b:
        return a
    if len(a) != len(b):
        return a  # Fallback
    return [x + y for x, y in zip(a, b)]


def vector_scale(v: List[float], scalar: float) -> List[float]:
    """Scale a vector by a scalar."""
    if not v or scalar == 0:
        return v or []
    return [x * scalar for x in v]


def compute_centroid(embeddings: List[List[float]]) -> List[float]:
    """Compute centroid (average) of a list of embeddings."""
    if not embeddings:
        return []
    if len(embeddings) == 1:
        return embeddings[0]
    
    dim = len(embeddings[0])
    centroid = [0.0] * dim
    for emb in embeddings:
        for i, v in enumerate(emb):
            centroid[i] += v
    
    n = len(embeddings)
    return [v / n for v in centroid]


class KnowShowGoAPI:
    """
    KnowShowGo API: A fuzzy ontology knowledge graph.
    
    KnowShowGo functions as a fuzzy ontology knowledge graph where:
    - Concepts have embeddings for similarity-based matching (fuzzy, not exact)
    - Relationships have confidence/strength scores (degrees of membership)
    - Embedding-based similarity provides the "fuzziness" (partial matches)
    - Supports uncertainty handling via provenance confidence scores
    
    Key features:
    - Embedding-first design: all concepts have embeddings for similarity matching
    - Threshold-based operations: similarity thresholds rather than exact matches
    - Multi-relationship support: concepts can have multiple relationship types
    - Fuzzy generalization: concepts can be generalized with similarity-based exemplar linking
    """

    def __init__(self, memory: MemoryTools, embed_fn: Optional[EmbedFn] = None):
        self.memory = memory
        self.embed_fn = embed_fn
        self.orm = KSGORM(memory)  # ORM for prototype-based object hydration

    def _normalize_result(self, result: Any) -> Dict[str, Any]:
        """Normalize a search result to a dict."""
        if isinstance(result, dict):
            return result
        if hasattr(result, "__dict__"):
            return result.__dict__
        return {}

    def _is_prototype(self, result: Dict[str, Any]) -> bool:
        """Check if a result is a prototype (kind=Prototype or isPrototype=True)."""
        kind = result.get("kind")
        if kind == "Prototype":
            return True
        props = result.get("props") or {}
        return props.get("isPrototype") is True

    def _find_prototype_uuid(self, name: str, top_k: int = 5) -> Optional[str]:
        """Find a prototype UUID by name with fallback logic."""
        # First try with topic filter
        results = self.memory.search(name, top_k=top_k, filters={"kind": "topic"})
        candidates = []
        for result in results:
            normalized = self._normalize_result(result)
            if self._is_prototype(normalized):
                candidates.append(normalized)
        # Fallback: search without filter
        if not candidates:
            results = self.memory.search(name, top_k=top_k)
            for result in results:
                normalized = self._normalize_result(result)
                if self._is_prototype(normalized):
                    candidates.append(normalized)
        if not candidates:
            return None
        # Prefer exact name match
        for candidate in candidates:
            labels = candidate.get("labels") or []
            props = candidate.get("props") or {}
            if name == props.get("label") or name == props.get("name") or name in labels:
                return candidate.get("uuid")
        # Return first candidate if no exact match
        return candidates[0].get("uuid")

    def create_prototype(
        self,
        name: str,
        description: str,
        context: str,
        labels: Optional[List[str]],
        embedding: List[float],
        provenance: Optional[Provenance] = None,
        base_prototype_uuid: Optional[str] = None,
    ) -> str:
        prov = provenance or Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo",
        )
        proto = Node(
            kind="Prototype",
            labels=labels or ["prototype"],
            props={"name": name, "description": description, "context": context},
            llm_embedding=embedding,
        )
        self.memory.upsert(proto, prov, embedding_request=True)
        if base_prototype_uuid:
            edge = Edge(
                from_node=proto.uuid,
                to_node=base_prototype_uuid,
                rel="inherits_from",
                props={"child": name, "parent_uuid": base_prototype_uuid},
            )
            self.memory.upsert(edge, prov, embedding_request=False)
        return proto.uuid

    def create_concept(
        self,
        prototype_uuid: str,
        json_obj: Dict[str, Any],
        embedding: List[float],
        provenance: Optional[Provenance] = None,
        previous_version_uuid: Optional[str] = None,
    ) -> str:
        prov = provenance or Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo",
        )
        concept = Node(
            kind="Concept",
            labels=[json_obj.get("name", "concept")],
            props={**json_obj, "prototype_uuid": prototype_uuid},
            llm_embedding=embedding,
        )
        self.memory.upsert(concept, prov, embedding_request=True)
        edge = Edge(
            from_node=concept.uuid,
            to_node=prototype_uuid,
            rel="instantiates",
            props={"prototype_uuid": prototype_uuid},
        )
        self.memory.upsert(edge, prov, embedding_request=False)
        if previous_version_uuid:
            version_edge = Edge(
                from_node=previous_version_uuid,
                to_node=concept.uuid,
                rel="next_version",
                props={"prototype_uuid": prototype_uuid},
            )
            self.memory.upsert(version_edge, prov, embedding_request=False)
        return concept.uuid

    def search_concepts(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        prototype_filter: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        hydrate: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fuzzy search for concepts by embedding similarity.
        
        In a fuzzy ontology, matching is based on similarity scores (cosine similarity
        of embeddings), not exact string matching. This enables finding "close enough"
        concepts even when names differ.
        
        Args:
            query: Search query text
            top_k: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0.0-1.0). Results below this are filtered out.
            prototype_filter: Optional prototype filter (requires edge traversal)
            query_embedding: Optional pre-computed query embedding
            hydrate: If True, automatically populate results with prototype properties (ORM-style)
            
        Returns:
            List of concept dicts with similarity scores (if available from memory backend).
            If hydrate=True, objects are populated with prototype properties + concept values.
        """
        if query_embedding is None and self.embed_fn:
            try:
                query_embedding = self.embed_fn(query)
            except Exception:
                query_embedding = None

        filters = {"kind": "Concept"}
        if prototype_filter:
            # Note: prototype filtering would require edge traversal, simplified here
            pass

        results = self.memory.search(query, top_k=top_k, filters=filters, query_embedding=query_embedding)
        
        if hydrate:
            # Use ORM to hydrate results
            return self.orm.query(query, top_k=top_k, hydrate=True)
        
        normalized = []
        for r in results:
            if isinstance(r, dict):
                normalized.append(r)
            elif hasattr(r, "__dict__"):
                normalized.append(r.__dict__)
        return normalized
    
    def get_concept_hydrated(self, concept_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get a concept and automatically hydrate it with prototype properties.
        
        This is the ORM-style method that:
        1. Loads the concept
        2. Finds its prototype (via instanceOf)
        3. Loads prototype property definitions
        4. Merges prototype properties (schema) with concept values
        5. Returns a hydrated object
        
        Args:
            concept_uuid: UUID of the concept to retrieve
            
        Returns:
            Hydrated object dict with prototype properties + concept values, or None if not found
        """
        return self.orm.get_concept(concept_uuid, hydrate=True)
    
    def create_object(self, prototype_name: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new concept object from a prototype name and properties (ORM-style).
        
        Similar to JavaScript: `new Person({name: "John", email: "john@example.com"})`
        
        Args:
            prototype_name: Name of the prototype (e.g., "Person", "Procedure")
            properties: Dictionary of property names to values
            
        Returns:
            Hydrated concept object
        """
        return self.orm.create_object(prototype_name, properties, embed_fn=self.embed_fn)
    
    def save_object(self, hydrated_obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save a hydrated object back to the knowledge graph (ORM-style).
        
        Updates the concept with new property values.
        
        Args:
            hydrated_obj: Hydrated concept object (from get_concept_hydrated or create_object)
            
        Returns:
            Updated hydrated object
        """
        return self.orm.save_object(hydrated_obj, embed_fn=self.embed_fn)
    
    def update_properties(self, concept_uuid: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update specific properties of a concept (ORM-style).
        
        Args:
            concept_uuid: UUID of the concept to update
            properties: Dictionary of property names to new values
            
        Returns:
            Updated hydrated object
        """
        return self.orm.update_properties(concept_uuid, properties, embed_fn=self.embed_fn)

    def create_concept_recursive(
        self,
        prototype_uuid: str,
        json_obj: Dict[str, Any],
        embedding: List[float],
        provenance: Optional[Provenance] = None,
        embed_fn: Optional[EmbedFn] = None,
    ) -> str:
        """
        Create a concept that may contain nested concepts (e.g., a Procedure DAG containing sub-procedures).
        Recursively creates child concepts if json_obj contains nested concept structures.
        """
        prov = provenance or Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo",
        )
        embed_fn = embed_fn or self.embed_fn

        # Extract nested concepts from json_obj (e.g., steps that are themselves concepts)
        nested_concepts_map = {}  # key -> list of nested concepts
        if isinstance(json_obj, dict):
            # Look for common nested structures: steps, children, sub_procedures, etc.
            for key in ["steps", "children", "sub_procedures", "sub_concepts", "nodes"]:
                if key in json_obj and isinstance(json_obj[key], list):
                    nested_concepts_map[key] = json_obj[key]

        # Create the main concept
        concept_uuid = self.create_concept(prototype_uuid, json_obj, embedding, provenance)

        # Recursively create nested concepts if they reference other prototypes
        # Recursion stops at atomic procedures (single tool commands)
        if nested_concepts_map and embed_fn:
            for key, nested_concepts in nested_concepts_map.items():
                for nested in nested_concepts:
                    if isinstance(nested, dict):
                        # Check if this is an atomic procedure (single tool command)
                        # Atomic = has a tool but no nested steps/children
                        is_atomic = (
                            nested.get("tool") is not None
                            and not nested.get("steps")
                            and not nested.get("children")
                            and not nested.get("sub_procedures")
                            and not nested.get("sub_concepts")
                        )
                        
                        # Handle nested items that reference prototypes
                        # Behavior differs by key:
                        # - "children": Create concepts even if atomic (has tool)
                        # - "steps": Only create concepts if non-atomic (has nested structure)
                        nested_proto_uuid = nested.get("prototype_uuid") or nested.get("prototype")
                        should_create_concept = nested_proto_uuid and (key == "children" or not is_atomic)
                        if should_create_concept:
                            nested_name = nested.get("name") or nested.get("title") or str(nested)
                            try:
                                nested_embedding = embed_fn(nested_name)
                                # Create nested concept recursively
                                nested_concept_uuid = self.create_concept_recursive(
                                    nested_proto_uuid, nested, nested_embedding, provenance, embed_fn
                                )
                                # Link parent -> child
                                rel_name = "has_child" if key == "children" else "has_step"
                                child_edge = Edge(
                                    from_node=concept_uuid,
                                    to_node=nested_concept_uuid,
                                    rel=rel_name,
                                    props={"order": nested.get("order", 0)},
                                )
                                self.memory.upsert(child_edge, prov, embedding_request=False)
                            except Exception:
                                pass  # Skip nested concept creation on error

        return concept_uuid

    def store_cpms_pattern(
        self,
        pattern_name: str,
        pattern_data: Dict[str, Any],
        embedding: List[float],
        concept_uuid: Optional[str] = None,
        provenance: Optional[Provenance] = None,
    ) -> str:
        """
        Store a CPMS pattern signal as a concept. Links to a parent concept if provided.
        Pattern data should include signal patterns (e.g., email input, password field, submit button).
        """
        prov = provenance or Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo-cpms",
        )

        # Find or create Pattern prototype
        pattern_proto = None
        try:
            proto_results = self.memory.search("Pattern", top_k=1, filters={"kind": "Prototype"})
            if proto_results:
                pattern_proto = proto_results[0]
                if isinstance(pattern_proto, dict):
                    pattern_proto_uuid = pattern_proto.get("uuid")
                else:
                    pattern_proto_uuid = getattr(pattern_proto, "uuid", None)
            else:
                # Create Pattern prototype if missing
                pattern_proto = Node(
                    kind="Prototype",
                    labels=["Prototype", "Pattern"],
                    props={"name": "Pattern", "description": "CPMS pattern signal", "context": "form_detection"},
                    llm_embedding=embedding[:10] if len(embedding) > 10 else embedding,  # Simplified
                )
                self.memory.upsert(pattern_proto, prov, embedding_request=True)
                pattern_proto_uuid = pattern_proto.uuid
        except Exception:
            pattern_proto_uuid = None

        if not pattern_proto_uuid:
            # Fallback: create as Concept directly
            pattern_node = Node(
                kind="Concept",
                labels=["Pattern", pattern_name],
                props={"name": pattern_name, "pattern_data": pattern_data, "source": "cpms"},
                llm_embedding=embedding,
            )
            self.memory.upsert(pattern_node, prov, embedding_request=True)
            pattern_uuid = pattern_node.uuid
        else:
            # Create concept linked to Pattern prototype
            pattern_concept = Node(
                kind="Concept",
                labels=["Pattern", pattern_name],
                props={"name": pattern_name, "pattern_data": pattern_data, "source": "cpms", "prototype_uuid": pattern_proto_uuid},
                llm_embedding=embedding,
            )
            self.memory.upsert(pattern_concept, prov, embedding_request=True)
            pattern_uuid = pattern_concept.uuid

            # Link to prototype
            inst_edge = Edge(
                from_node=pattern_uuid,
                to_node=pattern_proto_uuid,
                rel="instantiates",
                props={"prototype_uuid": pattern_proto_uuid},
            )
            self.memory.upsert(inst_edge, prov, embedding_request=False)

        # Link to parent concept if provided
        if concept_uuid:
            assoc_edge = Edge(
                from_node=concept_uuid,
                to_node=pattern_uuid,
                rel="has_pattern",
                props={"pattern_name": pattern_name},
            )
            self.memory.upsert(assoc_edge, prov, embedding_request=False)

        return pattern_uuid

    def generalize_concepts(
        self,
        exemplar_uuids: List[str],
        generalized_name: str,
        generalized_description: str,
        generalized_embedding: List[float],
        prototype_uuid: Optional[str] = None,
        provenance: Optional[Provenance] = None,
    ) -> str:
        """
        Merge multiple exemplar concepts into a generalized pattern.
        Creates a parent concept with generalized embedding and links exemplars as children.
        This creates a taxonomy/class hierarchy.
        """
        prov = provenance or Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo-generalize",
        )

        # Find or use provided prototype
        if not prototype_uuid:
            # Try to find Procedure or Concept prototype
            proto_results = self.memory.search("Procedure", top_k=1, filters={"kind": "Prototype"})
            if proto_results:
                prototype_uuid = proto_results[0].get("uuid") if isinstance(proto_results[0], dict) else getattr(proto_results[0], "uuid", None)

        # Create generalized parent concept
        generalized_json = {
            "name": generalized_name,
            "description": generalized_description,
            "type": "generalized",
            "exemplar_count": len(exemplar_uuids),
        }
        parent_uuid = self.create_concept(prototype_uuid or "unknown", generalized_json, generalized_embedding, provenance)

        # Link exemplars as children
        for idx, exemplar_uuid in enumerate(exemplar_uuids):
            child_edge = Edge(
                from_node=parent_uuid,
                to_node=exemplar_uuid,
                rel="has_exemplar",
                props={"order": idx, "generalized_from": parent_uuid},
            )
            self.memory.upsert(child_edge, prov, embedding_request=False)

            # Also create reverse edge for easy lookup
            parent_edge = Edge(
                from_node=exemplar_uuid,
                to_node=parent_uuid,
                rel="generalized_by",
                props={"generalized_name": generalized_name},
            )
            self.memory.upsert(parent_edge, prov, embedding_request=False)

        return parent_uuid

    def add_association(
        self,
        from_concept_uuid: str,
        to_concept_uuid: str,
        relation_type: str,
        strength: float = 1.0,
        props: Optional[Dict[str, Any]] = None,
        provenance: Optional[Provenance] = None,
    ) -> str:
        """
        Create a fuzzy association edge between two concepts.
        
        In a fuzzy ontology, relationships have degrees of strength (0.0-1.0),
        not just binary true/false. This enables uncertainty handling and
        partial membership in relationships.
        
        Args:
            from_concept_uuid: Source concept UUID
            to_concept_uuid: Target concept UUID
            relation_type: Type of relationship (e.g., "has_a", "uses", "contains", "depends_on", "associated_with")
            strength: Relationship strength (0.0-1.0), default 1.0 (strong). This is the fuzzy membership degree.
            props: Optional properties for the edge (strength will be added/overridden)
            provenance: Optional provenance
            
        Returns:
            Edge UUID
        """
        prov = provenance or Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo-assoc",
        )
        edge_props = props.copy() if props else {}
        edge_props["strength"] = strength  # Explicit fuzzy relationship strength
        edge = Edge(
            from_node=from_concept_uuid,
            to_node=to_concept_uuid,
            rel=relation_type,
            props=edge_props,
        )
        self.memory.upsert(edge, prov, embedding_request=False)
        return edge.uuid

    def find_best_cpms_pattern(
        self,
        url: str,
        html: str,
        form_type: Optional[str] = None,
        top_k: int = 1,
        search_limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the best stored CPMS pattern(s) for a given URL+HTML.

        This is a prototype-stage matcher:
        - strong preference for same-domain patterns
        - optional preference for matching form_type
        - token overlap between fingerprints
        """
        fp = compute_form_fingerprint(url=url, html=html).to_dict()
        fp_tokens = set(fp.get("tokens") or [])
        domain = (urlparse(url).netloc or "").lower()

        # Pull candidate concepts and filter down to CPMS Pattern concepts.
        candidates = self.memory.search(
            query_text=f"{domain} {form_type or ''}".strip(),
            top_k=search_limit,
            filters={"kind": "Concept"},
            query_embedding=self.embed_fn(f"{domain} {form_type}".strip()) if self.embed_fn else None,
        )
        patterns: List[Dict[str, Any]] = []
        for c in candidates:
            props = (c or {}).get("props") if isinstance(c, dict) else None
            if not isinstance(props, dict):
                continue
            if props.get("source") != "cpms":
                continue
            if "pattern_data" not in props:
                continue
            patterns.append(c)

        scored: List[Dict[str, Any]] = []
        for p in patterns:
            props = p.get("props") or {}
            pdata = props.get("pattern_data") if isinstance(props.get("pattern_data"), dict) else {}
            pfp = pdata.get("fingerprint") if isinstance(pdata.get("fingerprint"), dict) else {}
            p_tokens = set(pfp.get("tokens") or [])

            overlap = len(fp_tokens & p_tokens)
            union = len(fp_tokens | p_tokens) or 1
            jaccard = overlap / union

            p_domain = (pfp.get("domain") or "").lower()
            domain_bonus = 1.0 if p_domain and domain and p_domain == domain else 0.0
            type_bonus = 0.5 if form_type and pdata.get("form_type") == form_type else 0.0

            score = (2.0 * domain_bonus) + type_bonus + jaccard

            scored.append(
                {
                    "score": score,
                    "concept": p,
                    "pattern_data": pdata,
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[: max(0, top_k)]

    def create_object_with_properties(
        self,
        object_name: str,
        object_kind: str,
        properties: Dict[str, Any],
        prototype_uuid: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        provenance: Optional[Provenance] = None,
    ) -> Dict[str, Any]:
        """
        Create an object concept with properties, creating property concepts and has_a edges.
        
        For each property, creates:
        - A PropertyDef or property concept node
        - A "has_a" edge from object to property
        - Optionally an ObjectProperty node with property value
        
        Args:
            object_name: Name of the object
            object_kind: Kind/type of object (e.g., "Agent", "Place", "Device")
            properties: Dictionary of property_name -> property_value
            prototype_uuid: Optional prototype UUID (if None, uses Object prototype)
            embedding: Optional embedding for the object
            provenance: Optional provenance
            
        Returns:
            Dict with object_uuid, property_uuids, and edge_uuids
        """
        prov = provenance or Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo-object",
        )
        embed_fn = self.embed_fn
        
        # Find or use Object prototype
        if not prototype_uuid:
            proto_results = self.memory.search("Object", top_k=1, filters={"kind": "Prototype"})
            if proto_results:
                prototype_uuid = proto_results[0].get("uuid") if isinstance(proto_results[0], dict) else getattr(proto_results[0], "uuid", None)
        
        # Create object concept
        # Store object_name as "name", and merge properties
        # If properties contains "name", it will override object_name (properties take precedence for property values)
        object_json = {
            "name": object_name,  # Set object_name first
            "kind": object_kind,
            **properties,  # Properties may override "name" if it's in the properties dict
        }
        # But ensure object_name is preserved (object name should take precedence over property "name")
        object_json["name"] = object_name
        object_embedding = embedding or (embed_fn(object_name) if embed_fn else [0.0, 0.0])
        object_uuid = self.create_concept(prototype_uuid or "unknown", object_json, object_embedding, provenance)
        
        property_uuids = []
        edge_uuids = []
        object_property_uuids = []
        
        # Create property concepts and edges for each property
        for prop_name, prop_value in properties.items():
            # Create or find PropertyDef
            prop_def_uuid = None
            prop_def_results = self.memory.search(
                prop_name, top_k=1, filters={"kind": "PropertyDef"}
            )
            if prop_def_results:
                prop_def_uuid = prop_def_results[0].get("uuid") if isinstance(prop_def_results[0], dict) else getattr(prop_def_results[0], "uuid", None)
            else:
                # Create PropertyDef if not found
                if hasattr(self.memory, "nodes"):
                    # Create PropertyDef node
                    prop_def = Node(
                        kind="PropertyDef",
                        labels=["PropertyDef"],
                        props={"propertyName": prop_name, "dtype": "text"},
                        llm_embedding=embed_fn(f"{prop_name} property") if embed_fn else None,
                    )
                    self.memory.upsert(prop_def, prov, embedding_request=True)
                    prop_def_uuid = prop_def.uuid
            
            if prop_def_uuid:
                property_uuids.append(prop_def_uuid)
                
                # Create "has_a" edge from object to property definition
                has_a_edge = Edge(
                    from_node=object_uuid,
                    to_node=prop_def_uuid,
                    rel="has_a",
                    props={"property_name": prop_name, "property_value": prop_value},
                )
                self.memory.upsert(has_a_edge, prov, embedding_request=False)
                edge_uuids.append(has_a_edge.uuid)
                
                # Create ObjectProperty node with the actual value
                object_prop = Node(
                    kind="ObjectProperty",
                    labels=["ObjectProperty", prop_name],
                    props={
                        "object_uuid": object_uuid,
                        "property_name": prop_name,
                        "property_value": prop_value,
                        "property_def_uuid": prop_def_uuid,
                    },
                    llm_embedding=embed_fn(f"{object_name} {prop_name} {prop_value}") if embed_fn else None,
                )
                self.memory.upsert(object_prop, prov, embedding_request=True)
                object_property_uuids.append(object_prop.uuid)
                
                # Link ObjectProperty to object via "has_property" edge
                has_prop_edge = Edge(
                    from_node=object_uuid,
                    to_node=object_prop.uuid,
                    rel="has_property",
                    props={"property_name": prop_name},
                )
                self.memory.upsert(has_prop_edge, prov, embedding_request=False)
                edge_uuids.append(has_prop_edge.uuid)
        
        return {
            "object_uuid": object_uuid,
            "property_uuids": property_uuids,
            "edge_uuids": edge_uuids,
            "object_property_uuids": object_property_uuids,
        }

    # =========================================================================
    # CENTROID-BASED EMBEDDING EVOLUTION
    # Concepts evolve their embeddings based on exemplar centroids
    # =========================================================================

    def add_exemplar(
        self,
        concept_uuid: str,
        exemplar_embedding: List[float],
        exemplar_uuid: Optional[str] = None,
        provenance: Optional[Provenance] = None,
    ) -> Dict[str, Any]:
        """
        Add an exemplar to a concept and update its centroid embedding.
        
        The concept's embedding evolves to be the centroid (average) of all
        its exemplars. This allows concepts to "drift" toward their actual
        usage patterns over time.
        
        Args:
            concept_uuid: UUID of the concept/prototype to update
            exemplar_embedding: Embedding of the new exemplar
            exemplar_uuid: Optional UUID of the exemplar node (for linking)
            provenance: Optional provenance
            
        Returns:
            Dict with updated embedding info
        """
        prov = provenance or Provenance(
            source="exemplar",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo-centroid",
        )
        
        concept = self._get_concept_by_uuid(concept_uuid)
        if not concept:
            return {"error": "Concept not found", "updated": False}
        
        # Get current embedding state
        props = concept.get("props") or {}
        current_embedding = concept.get("llm_embedding") or []
        embedding_sum = props.get("_embedding_sum") or current_embedding
        exemplar_count = props.get("_exemplar_count", 1)
        
        # Update sum and count
        new_sum = vector_add(embedding_sum, exemplar_embedding)
        new_count = exemplar_count + 1
        
        # Compute new centroid
        new_centroid = vector_scale(new_sum, 1.0 / new_count)
        
        # Update concept
        updated_props = {
            **props,
            "_embedding_sum": new_sum,
            "_exemplar_count": new_count,
            "_last_exemplar_ts": datetime.now(timezone.utc).isoformat(),
        }
        
        updated_node = Node(
            uuid=concept_uuid,
            kind=concept.get("kind", "Concept"),
            labels=concept.get("labels", []),
            props=updated_props,
            llm_embedding=new_centroid,
        )
        self.memory.upsert(updated_node, prov, embedding_request=False)
        
        # Link exemplar if provided
        if exemplar_uuid:
            edge = Edge(
                from_node=concept_uuid,
                to_node=exemplar_uuid,
                rel="has_exemplar",
                props={"order": new_count - 1},
            )
            self.memory.upsert(edge, prov, embedding_request=False)
        
        return {
            "updated": True,
            "concept_uuid": concept_uuid,
            "exemplar_count": new_count,
            "embedding_drift": cosine_similarity(current_embedding, new_centroid) if current_embedding else 1.0,
        }

    def get_concept_centroid(self, concept_uuid: str) -> Optional[List[float]]:
        """
        Get the current centroid embedding for a concept.
        
        Returns the embedding which represents the average of all exemplars.
        """
        concept = self._get_concept_by_uuid(concept_uuid)
        if not concept:
            return None
        return concept.get("llm_embedding")

    def recompute_centroid(
        self,
        concept_uuid: str,
        provenance: Optional[Provenance] = None,
    ) -> Dict[str, Any]:
        """
        Recompute a concept's centroid from all linked exemplars.
        
        Useful after exemplars have been added/removed or for consistency checks.
        """
        prov = provenance or Provenance(
            source="recompute",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo-recompute",
        )
        
        concept = self._get_concept_by_uuid(concept_uuid)
        if not concept:
            return {"error": "Concept not found", "recomputed": False}
        
        # Collect all exemplar embeddings
        exemplar_embeddings = []
        
        # Check for linked exemplars via edges
        if hasattr(self.memory, "edges"):
            for edge_uuid, edge in self.memory.edges.items():
                if edge.from_node == concept_uuid and edge.rel == "has_exemplar":
                    exemplar = self._get_concept_by_uuid(edge.to_node)
                    if exemplar:
                        emb = exemplar.get("llm_embedding")
                        if emb:
                            exemplar_embeddings.append(emb)
        
        if not exemplar_embeddings:
            return {"recomputed": False, "reason": "no exemplars found"}
        
        # Compute new centroid
        new_centroid = compute_centroid(exemplar_embeddings)
        new_sum = [0.0] * len(new_centroid)
        for emb in exemplar_embeddings:
            new_sum = vector_add(new_sum, emb)
        
        # Update concept
        props = concept.get("props") or {}
        updated_props = {
            **props,
            "_embedding_sum": new_sum,
            "_exemplar_count": len(exemplar_embeddings),
            "_recomputed_ts": datetime.now(timezone.utc).isoformat(),
        }
        
        updated_node = Node(
            uuid=concept_uuid,
            kind=concept.get("kind", "Concept"),
            labels=concept.get("labels", []),
            props=updated_props,
            llm_embedding=new_centroid,
        )
        self.memory.upsert(updated_node, prov, embedding_request=False)
        
        return {
            "recomputed": True,
            "concept_uuid": concept_uuid,
            "exemplar_count": len(exemplar_embeddings),
        }

    # =========================================================================
    # FIRST-CLASS EDGES (Edge as Node with mirrored attributes)
    # Future: Full implementation in separate KnowShowGo repo
    # =========================================================================

    def create_relationship(
        self,
        from_uuid: str,
        to_uuid: str,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
        provenance: Optional[Provenance] = None,
    ) -> Dict[str, Any]:
        """
        Create a first-class relationship (edge as node).
        
        This creates:
        1. A Relationship node with the edge properties and embedding
        2. Edges connecting from_node → relationship → to_node
        3. Mirrored attributes on both endpoints
        
        This enables searching for relationships by similarity.
        
        Args:
            from_uuid: Source node UUID
            to_uuid: Target node UUID
            rel_type: Relationship type (e.g., "uses", "depends_on", "similar_to")
            properties: Optional properties for the relationship
            embedding: Optional embedding for the relationship (for similarity search)
            provenance: Optional provenance
            
        Returns:
            Dict with relationship_uuid and edge_uuids
        """
        prov = provenance or Provenance(
            source="relationship",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo-rel",
        )
        
        props = properties or {}
        
        # Generate embedding if not provided and we have embed_fn
        if not embedding and self.embed_fn:
            # Get names of connected nodes for embedding
            from_node = self._get_concept_by_uuid(from_uuid)
            to_node = self._get_concept_by_uuid(to_uuid)
            from_name = (from_node or {}).get("props", {}).get("name", "")
            to_name = (to_node or {}).get("props", {}).get("name", "")
            try:
                embedding = self.embed_fn(f"{from_name} {rel_type} {to_name}")
            except Exception:
                embedding = None
        
        # Create Relationship node (edge as first-class citizen)
        rel_node = Node(
            kind="Relationship",
            labels=["Relationship", rel_type],
            props={
                **props,
                "rel_type": rel_type,
                "from_uuid": from_uuid,
                "to_uuid": to_uuid,
            },
            llm_embedding=embedding,
        )
        self.memory.upsert(rel_node, prov, embedding_request=bool(embedding))
        
        # Create edges: from → rel, rel → to
        from_edge = Edge(
            from_node=from_uuid,
            to_node=rel_node.uuid,
            rel="has_outgoing",
            props={"rel_type": rel_type},
        )
        to_edge = Edge(
            from_node=rel_node.uuid,
            to_node=to_uuid,
            rel="points_to",
            props={"rel_type": rel_type},
        )
        self.memory.upsert(from_edge, prov, embedding_request=False)
        self.memory.upsert(to_edge, prov, embedding_request=False)
        
        # Mirror attributes on endpoints (simplified version)
        # Full implementation would update from_node and to_node with relationship references
        # This is deferred to separate KnowShowGo repo for full implementation
        
        return {
            "relationship_uuid": rel_node.uuid,
            "from_edge_uuid": from_edge.uuid,
            "to_edge_uuid": to_edge.uuid,
            "rel_type": rel_type,
        }

    def search_relationships(
        self,
        query: str,
        rel_type: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Search for relationships by similarity.
        
        Because relationships are first-class nodes with embeddings,
        we can search for similar relationships.
        
        Args:
            query: Search query (e.g., "authentication dependency")
            rel_type: Optional filter by relationship type
            top_k: Maximum results
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of matching relationships
        """
        query_embedding = None
        if self.embed_fn:
            try:
                query_embedding = self.embed_fn(query)
            except Exception:
                pass
        
        filters = {"kind": "Relationship"}
        results = self.memory.search(
            query,
            top_k=top_k * 2,
            filters=filters,
            query_embedding=query_embedding,
        )
        
        relationships = []
        for r in results:
            normalized = self._normalize_result(r)
            props = normalized.get("props") or {}
            
            # Filter by rel_type if specified
            if rel_type and props.get("rel_type") != rel_type:
                continue
            
            # Calculate similarity if we have embeddings
            similarity = 0.7  # Default
            stored_emb = normalized.get("llm_embedding")
            if query_embedding and stored_emb:
                similarity = cosine_similarity(query_embedding, stored_emb)
            
            if similarity >= min_similarity:
                relationships.append({
                    "uuid": normalized.get("uuid"),
                    "rel_type": props.get("rel_type"),
                    "from_uuid": props.get("from_uuid"),
                    "to_uuid": props.get("to_uuid"),
                    "similarity": similarity,
                    "props": props,
                })
        
        relationships.sort(key=lambda x: x["similarity"], reverse=True)
        return relationships[:top_k]

    # =========================================================================
    # PATTERN EVOLUTION METHODS
    # These methods support the Learn → Recall → Execute → Adapt → Generalize loop
    # =========================================================================

    def find_similar_patterns(
        self,
        query: str,
        pattern_type: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.5,
        exclude_uuids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find patterns similar to the query that could be transferred to a new situation.
        
        This is the foundation of pattern transfer - finding existing knowledge
        that might apply to a novel situation.
        
        Args:
            query: Description of the target situation (e.g., "checkout form on amazon.com")
            pattern_type: Optional filter (e.g., "Procedure", "Pattern", "FormPattern")
            top_k: Maximum results to return
            min_similarity: Minimum similarity threshold (0.0-1.0)
            exclude_uuids: UUIDs to exclude from results
            
        Returns:
            List of similar patterns with similarity scores, sorted by relevance
        """
        exclude_uuids = exclude_uuids or []
        
        # Generate query embedding
        query_embedding = None
        if self.embed_fn:
            try:
                query_embedding = self.embed_fn(query)
            except Exception as e:
                logger.warning(f"Failed to generate query embedding: {e}")
        
        # Search for similar concepts
        filters = {"kind": "Concept"}
        results = self.memory.search(
            query,
            top_k=top_k * 3,  # Get more results to filter
            filters=filters,
            query_embedding=query_embedding,
        )
        
        similar_patterns = []
        for r in results:
            normalized = self._normalize_result(r)
            uuid = normalized.get("uuid")
            
            # Skip excluded UUIDs
            if uuid in exclude_uuids:
                continue
            
            # Filter by pattern type if specified
            props = normalized.get("props") or {}
            labels = normalized.get("labels") or []
            
            if pattern_type:
                is_match = (
                    pattern_type in labels or
                    props.get("type") == pattern_type or
                    props.get("pattern_type") == pattern_type or
                    normalized.get("kind") == pattern_type
                )
                if not is_match:
                    continue
            
            # Calculate similarity if we have embeddings
            similarity = 0.7  # Default if no embeddings
            stored_embedding = normalized.get("llm_embedding")
            if query_embedding and stored_embedding:
                similarity = cosine_similarity(query_embedding, stored_embedding)
            
            if similarity >= min_similarity:
                similar_patterns.append({
                    "uuid": uuid,
                    "name": props.get("name") or labels[0] if labels else "unknown",
                    "similarity": similarity,
                    "props": props,
                    "labels": labels,
                    "pattern_data": props.get("pattern_data"),
                    "steps": props.get("steps"),
                    "selectors": props.get("selectors"),
                })
        
        # Sort by similarity
        similar_patterns.sort(key=lambda x: x["similarity"], reverse=True)
        return similar_patterns[:top_k]

    def transfer_pattern(
        self,
        source_pattern_uuid: str,
        target_context: Dict[str, Any],
        llm_fn: Optional[LLMFn] = None,
        provenance: Optional[Provenance] = None,
    ) -> Dict[str, Any]:
        """
        Transfer a pattern from one context to another using LLM reasoning.
        
        This is the core of pattern transfer - taking a working pattern and
        adapting it to a new, similar situation.
        
        Args:
            source_pattern_uuid: UUID of the source pattern to transfer
            target_context: Information about the target situation:
                - url: Target URL (if web-related)
                - fields: List of field names/labels in target
                - form_type: Type of form (login, checkout, survey, etc.)
                - description: Description of target task
            llm_fn: Function to call LLM for reasoning (prompt -> response)
            provenance: Optional provenance
            
        Returns:
            Dict with:
                - transferred_pattern: The adapted pattern
                - field_mapping: How fields were mapped
                - confidence: Confidence in the transfer
                - new_pattern_uuid: UUID of stored transferred pattern (if stored)
        """
        prov = provenance or Provenance(
            source="transfer",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=0.8,
            trace_id="knowshowgo-transfer",
        )
        
        # Load source pattern
        source = self._get_concept_by_uuid(source_pattern_uuid)
        if not source:
            return {"error": "Source pattern not found", "transferred_pattern": None}
        
        source_props = source.get("props") or {}
        
        # Selectors may be in pattern_data (from store_cpms_pattern) or directly in props
        pattern_data = source_props.get("pattern_data") or {}
        if isinstance(pattern_data, dict):
            source_selectors = pattern_data.get("selectors") or source_props.get("selectors") or {}
            source_steps = pattern_data.get("steps") or source_props.get("steps") or []
        else:
            source_selectors = source_props.get("selectors") or {}
            source_steps = source_props.get("steps") or []
        
        source_fields = list(source_selectors.keys()) if source_selectors else []
        
        target_fields = target_context.get("fields") or []
        target_url = target_context.get("url", "")
        target_description = target_context.get("description", "")
        
        # If no LLM function provided, do simple field name matching
        if not llm_fn:
            field_mapping = self._simple_field_mapping(source_fields, target_fields)
            confidence = 0.6
        else:
            # Use LLM to reason about the transfer
            prompt = self._build_transfer_prompt(
                source_name=source_props.get("name", "unknown"),
                source_fields=source_fields,
                source_selectors=source_selectors,
                target_fields=target_fields,
                target_url=target_url,
                target_description=target_description,
            )
            
            try:
                llm_response = llm_fn(prompt)
                field_mapping, confidence = self._parse_transfer_response(llm_response)
            except Exception as e:
                logger.warning(f"LLM transfer failed: {e}, falling back to simple mapping")
                field_mapping = self._simple_field_mapping(source_fields, target_fields)
                confidence = 0.5
        
        # Build transferred pattern
        transferred_selectors = {}
        for target_field, source_field in field_mapping.items():
            if source_field and source_field in source_selectors:
                # Adapt the selector for the new context
                transferred_selectors[target_field] = self._adapt_selector(
                    source_selectors[source_field],
                    target_field
                )
        
        # Build transferred steps (if procedure)
        transferred_steps = []
        for step in source_steps:
            transferred_step = step.copy()
            params = transferred_step.get("params", {})
            # Update URL if present
            if "url" in params and target_url:
                transferred_step["params"] = {**params, "url": target_url}
            # Update selectors in params
            if "selector" in params:
                for target_field, source_field in field_mapping.items():
                    if source_field in params["selector"]:
                        transferred_step["params"]["selector"] = params["selector"].replace(
                            source_field, target_field
                        )
            transferred_steps.append(transferred_step)
        
        transferred_pattern = {
            "name": f"Transferred: {source_props.get('name', 'pattern')} → {target_url or target_description}",
            "source_pattern_uuid": source_pattern_uuid,
            "selectors": transferred_selectors,
            "steps": transferred_steps if transferred_steps else None,
            "field_mapping": field_mapping,
            "target_url": target_url,
            "transfer_confidence": confidence,
            "type": "transferred",
        }
        
        # Store the transferred pattern if confidence is high enough
        new_pattern_uuid = None
        if confidence >= 0.6 and self.embed_fn:
            try:
                embedding = self.embed_fn(
                    f"{transferred_pattern['name']} {target_url} {' '.join(target_fields)}"
                )
                new_pattern_uuid = self.store_cpms_pattern(
                    pattern_name=transferred_pattern["name"],
                    pattern_data=transferred_pattern,
                    embedding=embedding,
                    concept_uuid=source_pattern_uuid,  # Link to source
                    provenance=prov,
                )
                
                # Create transfer edge
                self.add_association(
                    from_concept_uuid=source_pattern_uuid,
                    to_concept_uuid=new_pattern_uuid,
                    relation_type="transferred_to",
                    strength=confidence,
                    props={"field_mapping": field_mapping},
                    provenance=prov,
                )
            except Exception as e:
                logger.warning(f"Failed to store transferred pattern: {e}")
        
        return {
            "transferred_pattern": transferred_pattern,
            "field_mapping": field_mapping,
            "confidence": confidence,
            "new_pattern_uuid": new_pattern_uuid,
        }

    def record_pattern_success(
        self,
        pattern_uuid: str,
        context: Optional[Dict[str, Any]] = None,
        provenance: Optional[Provenance] = None,
    ) -> Dict[str, Any]:
        """
        Record a successful pattern application. This feeds into auto-generalization.
        
        Args:
            pattern_uuid: UUID of the pattern that succeeded
            context: Optional context about the success (url, fields filled, etc.)
            provenance: Optional provenance
            
        Returns:
            Dict with success_count and whether generalization was triggered
        """
        prov = provenance or Provenance(
            source="execution",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo-success",
        )
        
        # Get current pattern
        pattern = self._get_concept_by_uuid(pattern_uuid)
        if not pattern:
            return {"error": "Pattern not found", "success_count": 0}
        
        # Get props - handle both dict and direct attribute access
        if isinstance(pattern, dict):
            props = pattern.get("props") or {}
            kind = pattern.get("kind", "Concept")
            labels = pattern.get("labels", [])
            embedding = pattern.get("llm_embedding")
        else:
            props = getattr(pattern, "props", {}) or {}
            kind = getattr(pattern, "kind", "Concept")
            labels = getattr(pattern, "labels", [])
            embedding = getattr(pattern, "llm_embedding", None)
        
        success_count = props.get("success_count", 0) + 1
        
        # Update success count
        updated_props = {
            **props,
            "success_count": success_count,
            "last_success": datetime.now(timezone.utc).isoformat(),
            "last_success_context": context,
        }
        
        # Update the concept
        updated_node = Node(
            uuid=pattern_uuid,
            kind=kind,
            labels=labels if isinstance(labels, list) else list(labels) if labels else [],
            props=updated_props,
            llm_embedding=embedding,
        )
        self.memory.upsert(updated_node, prov, embedding_request=False)
        
        return {
            "success_count": success_count,
            "pattern_uuid": pattern_uuid,
        }

    def auto_generalize(
        self,
        pattern_uuid: str,
        min_similar: int = 2,
        min_similarity: float = 0.75,
        llm_fn: Optional[LLMFn] = None,
        provenance: Optional[Provenance] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Automatically detect and merge similar successful patterns into a generalized pattern.
        
        Called after a pattern succeeds. Checks if there are enough similar successful
        patterns to warrant generalization.
        
        Args:
            pattern_uuid: UUID of the pattern that just succeeded
            min_similar: Minimum number of similar patterns needed to generalize
            min_similarity: Minimum similarity threshold for patterns to be grouped
            llm_fn: Optional LLM function for generating generalized description
            provenance: Optional provenance
            
        Returns:
            Dict with generalized pattern info, or None if no generalization occurred
        """
        prov = provenance or Provenance(
            source="auto-generalize",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=0.9,
            trace_id="knowshowgo-generalize",
        )
        
        # Get the triggering pattern
        pattern = self._get_concept_by_uuid(pattern_uuid)
        if not pattern:
            return None
        
        props = pattern.get("props") or {}
        pattern_name = props.get("name", "")
        
        # Check if already generalized
        if props.get("type") == "generalized":
            return None
        
        # Check if already has a parent generalization
        # (We don't want to re-generalize exemplars)
        if props.get("generalized_by"):
            return None
        
        # Find similar successful patterns
        similar = self.find_similar_patterns(
            query=pattern_name,
            top_k=10,
            min_similarity=min_similarity,
            exclude_uuids=[pattern_uuid],
        )
        
        # Filter to only successful patterns
        successful_similar = []
        for s in similar:
            s_props = s.get("props") or {}
            if s_props.get("success_count", 0) > 0:
                successful_similar.append(s)
        
        # Check if we have enough similar successful patterns
        if len(successful_similar) < min_similar - 1:  # -1 because we count the trigger pattern
            return None
        
        # Collect exemplar UUIDs (including the triggering pattern)
        exemplar_uuids = [pattern_uuid] + [s["uuid"] for s in successful_similar[:min_similar - 1]]
        
        # Generate generalized name and description
        exemplar_names = [pattern_name] + [s.get("name", "") for s in successful_similar[:min_similar - 1]]
        
        if llm_fn:
            generalized_name, generalized_description = self._generate_generalization_with_llm(
                exemplar_names, llm_fn
            )
        else:
            generalized_name = self._extract_common_pattern(exemplar_names)
            generalized_description = f"Generalized pattern from {len(exemplar_uuids)} similar patterns"
        
        # Generate embedding for generalized concept (average of exemplars)
        generalized_embedding = self._average_embeddings(exemplar_uuids)
        
        # Create generalized pattern
        generalized_uuid = self.generalize_concepts(
            exemplar_uuids=exemplar_uuids,
            generalized_name=generalized_name,
            generalized_description=generalized_description,
            generalized_embedding=generalized_embedding,
            provenance=prov,
        )
        
        # Extract common selectors/steps
        common_selectors = self._extract_common_selectors(exemplar_uuids)
        common_steps = self._extract_common_steps(exemplar_uuids)
        
        # Update generalized pattern with common elements
        if common_selectors or common_steps:
            gen_pattern = self._get_concept_by_uuid(generalized_uuid)
            if gen_pattern:
                gen_props = gen_pattern.get("props") or {}
                gen_props["common_selectors"] = common_selectors
                gen_props["common_steps"] = common_steps
                gen_props["exemplar_count"] = len(exemplar_uuids)
                
                updated_node = Node(
                    uuid=generalized_uuid,
                    kind=gen_pattern.get("kind", "Concept"),
                    labels=gen_pattern.get("labels", []),
                    props=gen_props,
                    llm_embedding=gen_pattern.get("llm_embedding"),
                )
                self.memory.upsert(updated_node, prov, embedding_request=False)
        
        logger.info(f"Auto-generalized {len(exemplar_uuids)} patterns into '{generalized_name}'")
        
        return {
            "generalized_uuid": generalized_uuid,
            "generalized_name": generalized_name,
            "exemplar_count": len(exemplar_uuids),
            "exemplar_uuids": exemplar_uuids,
            "common_selectors": common_selectors,
            "common_steps": common_steps,
        }

    def find_generalized_pattern(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.6,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a generalized pattern that matches the query.
        
        Generalized patterns are preferred because they represent proven,
        cross-situation knowledge.
        
        Args:
            query: Description of the target situation
            top_k: Number of candidates to consider
            min_similarity: Minimum similarity threshold
            
        Returns:
            Best matching generalized pattern, or None
        """
        similar = self.find_similar_patterns(
            query=query,
            top_k=top_k * 2,
            min_similarity=min_similarity,
        )
        
        # Prefer generalized patterns
        for s in similar:
            props = s.get("props") or {}
            if props.get("type") == "generalized":
                return s
        
        return None

    # =========================================================================
    # HELPER METHODS FOR PATTERN EVOLUTION
    # =========================================================================

    def _get_concept_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get a concept by UUID."""
        # Try direct lookup first if memory has nodes dict
        if hasattr(self.memory, "nodes") and uuid in self.memory.nodes:
            node = self.memory.nodes[uuid]
            if hasattr(node, "__dict__"):
                return node.__dict__
            return node
        
        # Fallback to search
        results = self.memory.search(uuid, top_k=10)
        for r in results:
            normalized = self._normalize_result(r)
            if normalized.get("uuid") == uuid:
                return normalized
        return None

    def _simple_field_mapping(
        self,
        source_fields: List[str],
        target_fields: List[str],
    ) -> Dict[str, str]:
        """Simple field mapping based on name similarity."""
        mapping = {}
        used_sources = set()
        
        # Normalize field names for matching
        def normalize(name: str) -> str:
            return name.lower().replace("_", "").replace("-", "").replace(" ", "")
        
        for target in target_fields:
            target_norm = normalize(target)
            best_match = None
            best_score = 0
            
            for source in source_fields:
                if source in used_sources:
                    continue
                source_norm = normalize(source)
                
                # Exact match
                if source_norm == target_norm:
                    best_match = source
                    best_score = 1.0
                    break
                
                # Substring match
                if source_norm in target_norm or target_norm in source_norm:
                    score = min(len(source_norm), len(target_norm)) / max(len(source_norm), len(target_norm))
                    if score > best_score:
                        best_match = source
                        best_score = score
            
            if best_match and best_score >= 0.5:
                mapping[target] = best_match
                used_sources.add(best_match)
        
        return mapping

    def _build_transfer_prompt(
        self,
        source_name: str,
        source_fields: List[str],
        source_selectors: Dict[str, str],
        target_fields: List[str],
        target_url: str,
        target_description: str,
    ) -> str:
        """Build prompt for LLM-assisted pattern transfer."""
        return f"""You are helping transfer a form-filling pattern to a new context.

SOURCE PATTERN: "{source_name}"
Source fields: {json.dumps(source_fields)}
Source selectors: {json.dumps(source_selectors)}

TARGET CONTEXT:
URL: {target_url}
Description: {target_description}
Target fields: {json.dumps(target_fields)}

Task: Map each target field to the most appropriate source field.
Consider semantic similarity (e.g., "email" matches "email_address", "username" matches "login").

Respond with JSON only:
{{
    "field_mapping": {{"target_field": "source_field", ...}},
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

    def _parse_transfer_response(
        self,
        response: str,
    ) -> Tuple[Dict[str, str], float]:
        """Parse LLM response for transfer mapping."""
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                return data.get("field_mapping", {}), data.get("confidence", 0.7)
        except Exception:
            pass
        return {}, 0.5

    def _adapt_selector(self, source_selector: str, target_field: str) -> str:
        """Adapt a selector for a new field context."""
        # Common selector patterns
        common_selectors = [
            f"#{target_field}",
            f"[name='{target_field}']",
            f"[id='{target_field}']",
            f"input[name='{target_field}']",
        ]
        return common_selectors[0]  # Return most common pattern

    def _extract_common_pattern(self, names: List[str]) -> str:
        """Extract common pattern from a list of names."""
        if not names:
            return "Generalized Pattern"
        
        # Find common words
        word_sets = [set(name.lower().split()) for name in names if name]
        if not word_sets:
            return "Generalized Pattern"
        
        common_words = word_sets[0]
        for ws in word_sets[1:]:
            common_words &= ws
        
        # Remove common stopwords
        stopwords = {"the", "a", "an", "to", "for", "on", "in", "at", "form", "pattern"}
        common_words -= stopwords
        
        if common_words:
            return f"Generalized {' '.join(sorted(common_words)).title()}"
        
        return "Generalized Pattern"

    def _generate_generalization_with_llm(
        self,
        exemplar_names: List[str],
        llm_fn: LLMFn,
    ) -> Tuple[str, str]:
        """Use LLM to generate a good name and description for generalized pattern."""
        prompt = f"""Given these similar pattern names:
{json.dumps(exemplar_names)}

Generate a generalized name and description that captures their common essence.

Respond with JSON only:
{{"name": "short generalized name", "description": "what this pattern does"}}"""
        
        try:
            response = llm_fn(prompt)
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                return data.get("name", "Generalized Pattern"), data.get("description", "")
        except Exception:
            pass
        
        return self._extract_common_pattern(exemplar_names), f"Generalized from {len(exemplar_names)} patterns"

    def _average_embeddings(self, uuids: List[str]) -> List[float]:
        """Compute average embedding from multiple concepts."""
        embeddings = []
        for uuid in uuids:
            concept = self._get_concept_by_uuid(uuid)
            if concept:
                emb = concept.get("llm_embedding")
                if emb:
                    embeddings.append(emb)
        
        if not embeddings:
            return [0.0] * 10  # Fallback
        
        # Average the embeddings
        dim = len(embeddings[0])
        avg = [0.0] * dim
        for emb in embeddings:
            for i, v in enumerate(emb):
                avg[i] += v
        
        return [v / len(embeddings) for v in avg]

    def _extract_common_selectors(self, uuids: List[str]) -> Dict[str, List[str]]:
        """Extract common selectors across patterns."""
        all_selectors: Dict[str, List[str]] = {}
        
        for uuid in uuids:
            concept = self._get_concept_by_uuid(uuid)
            if not concept:
                continue
            props = concept.get("props") or {}
            selectors = props.get("selectors") or {}
            
            for field, selector in selectors.items():
                if field not in all_selectors:
                    all_selectors[field] = []
                all_selectors[field].append(selector)
        
        # Keep fields that appear in most patterns
        threshold = len(uuids) * 0.5
        common = {}
        for field, selectors in all_selectors.items():
            if len(selectors) >= threshold:
                common[field] = selectors
        
        return common

    def _extract_common_steps(self, uuids: List[str]) -> List[Dict[str, Any]]:
        """Extract common step structure across patterns."""
        all_steps: List[List[Dict[str, Any]]] = []
        
        for uuid in uuids:
            concept = self._get_concept_by_uuid(uuid)
            if not concept:
                continue
            props = concept.get("props") or {}
            steps = props.get("steps") or []
            if steps:
                all_steps.append(steps)
        
        if not all_steps:
            return []
        
        # Find common step structure (by tool sequence)
        min_len = min(len(s) for s in all_steps)
        common_steps = []
        
        for i in range(min_len):
            tools_at_i = [s[i].get("tool") for s in all_steps if i < len(s)]
            # If all have same tool at position i, include it
            if len(set(tools_at_i)) == 1:
                # Use first pattern's step as template
                common_steps.append({
                    "position": i,
                    "tool": tools_at_i[0],
                    "template": all_steps[0][i],
                })
        
        return common_steps
