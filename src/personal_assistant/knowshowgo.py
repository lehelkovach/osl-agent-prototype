from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools
from src.personal_assistant.ksg_orm import KSGORM


EmbedFn = Callable[[str], List[float]]


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
        """
        Create a Prototype (Topic with isPrototype=true).
        
        Aligned with Knowshowgo v0.1: Prototypes are Topics with isPrototype=true.
        """
        prov = provenance or Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo",
        )
        # Create Prototype as Topic with isPrototype=true
        proto_labels = labels or [name]
        proto = Node(
            kind="topic",  # All nodes are Topics in Knowshowgo
            labels=proto_labels,
            props={
                "label": name,  # Primary label
                "aliases": proto_labels[1:] if len(proto_labels) > 1 else [],  # Additional labels
                "summary": description,
                "isPrototype": True,  # Mark as Prototype
                "status": "active",
                "namespace": "public",
                "context": context,  # Additional context
                # Backward compat
                "name": name,
                "description": description,
            },
            llm_embedding=embedding,
        )
        self.memory.upsert(proto, prov, embedding_request=True)
        if base_prototype_uuid:
            # Use inherits edge (Knowshowgo design)
            edge = Edge(
                from_node=proto.uuid,
                to_node=base_prototype_uuid,
                rel="inherits",  # Knowshowgo: inherits edge collection
                props={
                    "child": name,
                    "parent_uuid": base_prototype_uuid,
                    "w": 1.0,  # Weight
                    "status": "accepted",
                },
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
        """
        Create a Concept (Topic with isPrototype=false).
        
        Aligned with Knowshowgo v0.1: Concepts are Topics with isPrototype=false.
        Uses instanceOf association to link to Prototype.
        """
        prov = provenance or Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo",
        )
        # Extract label and aliases from json_obj
        label = json_obj.get("name") or json_obj.get("label") or "concept"
        aliases = json_obj.get("aliases", [])
        if label not in aliases:
            aliases = [label] + aliases
        
        # Create Concept as Topic with isPrototype=false
        concept = Node(
            kind="topic",  # All nodes are Topics in Knowshowgo
            labels=aliases,  # Primary label + aliases
            props={
                "label": label,  # Primary label
                "aliases": aliases[1:] if len(aliases) > 1 else [],  # Additional labels
                "summary": json_obj.get("description") or json_obj.get("summary", ""),
                "isPrototype": False,  # Mark as Concept (not Prototype)
                "status": "active",
                "namespace": "public",
                "prototype_uuid": prototype_uuid,  # Backward compat
                **{k: v for k, v in json_obj.items() if k not in ("name", "label", "aliases", "description", "summary")},
            },
            llm_embedding=embedding,
        )
        self.memory.upsert(concept, prov, embedding_request=True)
        
        # Create instanceOf association (Knowshowgo: instanceOf PropertyDef)
        # Use add_association to get PropertyDef reference
        self.add_association(
            from_concept_uuid=concept.uuid,
            to_concept_uuid=prototype_uuid,
            relation_type="instanceOf",
            strength=1.0,
            provenance=prov,
        )
        
        if previous_version_uuid:
            # Version chain edge
            version_edge = Edge(
                from_node=previous_version_uuid,
                to_node=concept.uuid,
                rel="next_version",
                props={
                    "prototype_uuid": prototype_uuid,
                    "w": 1.0,
                    "status": "accepted",
                },
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

        filters = {"kind": "topic"}  # All nodes are topics in Knowshowgo
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
        
        Similar to JavaScript prototype-based OOP where:
        - Prototype defines properties (schema)
        - Concept provides values (instance data)
        - Object automatically has all prototype properties + concept values
        
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
        
        Updates the concept with new property values. Similar to JavaScript object assignment.
        
        Args:
            hydrated_obj: Hydrated concept object (from get_concept_hydrated or create_object)
            
        Returns:
            Updated hydrated object
        """
        return self.orm.save_object(hydrated_obj, embed_fn=self.embed_fn)
    
    def update_properties(self, concept_uuid: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update specific properties of a concept (ORM-style).
        
        Similar to JavaScript: `object.property = value` or `Object.assign(object, {property: value})`
        
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
        property_def_uuid: Optional[str] = None,
    ) -> str:
        """
        Create a fuzzy association edge between two concepts (Topics).
        
        Aligned with Knowshowgo v0.1 Association model:
        - Properties-as-edges with PropertyDef reference (p)
        - Weight (w) for fuzzy association strength (0.0-1.0)
        - Confidence, provenance, status
        
        In a fuzzy ontology, relationships have degrees of strength (0.0-1.0),
        not just binary true/false. This enables uncertainty handling and
        partial membership in relationships.
        
        Args:
            from_concept_uuid: Source concept/topic UUID
            to_concept_uuid: Target concept/topic UUID
            relation_type: Type of relationship (e.g., "hasStep", "relatedTo", "instanceOf")
            strength: Relationship weight/strength (0.0-1.0), default 1.0 (strong). Stored as "w".
            props: Optional properties for the edge (w, p, confidence, status will be added/overridden)
            provenance: Optional provenance
            property_def_uuid: Optional PropertyDef UUID reference (p field). If None, will search for PropertyDef by relation_type.
            
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
        
        # Find or use PropertyDef reference (p field per Knowshowgo design)
        prop_def_uuid = property_def_uuid
        if not prop_def_uuid:
            # Search for PropertyDef by relation_type name
            try:
                prop_def_results = self.memory.search(
                    relation_type, top_k=1, filters={"kind": "PropertyDef"}
                )
                if prop_def_results:
                    prop_def_uuid = prop_def_results[0].get("uuid") if isinstance(prop_def_results[0], dict) else getattr(prop_def_results[0], "uuid", None)
            except Exception:
                pass  # Continue without PropertyDef reference if search fails
        
        # Set Knowshowgo Association fields
        edge_props["w"] = strength  # Weight (primary fuzzy association strength)
        edge_props["strength"] = strength  # Backward compat
        if prop_def_uuid:
            edge_props["p"] = prop_def_uuid  # PropertyDef reference (predicate)
        edge_props["confidence"] = prov.confidence  # From provenance
        edge_props["status"] = edge_props.get("status", "accepted")  # Default to accepted
        edge_props["provenance"] = {
            "type": prov.source,
            "trace_id": prov.trace_id,
            "ts": prov.ts,
        }
        
        edge = Edge(
            from_node=from_concept_uuid,
            to_node=to_concept_uuid,
            rel=relation_type,  # Backward compat (also stored in props if needed)
            props=edge_props,
        )
        self.memory.upsert(edge, prov, embedding_request=False)
        return edge.uuid

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
