"""
Knowshowgo ORM: Prototype-based object hydration.

This module provides an ORM-like interface that automatically populates objects
with prototype properties and concept values, similar to JavaScript prototype-based OOP.

When querying for a KSG object (concept):
1. Loads the concept (Topic with isPrototype=false)
2. Finds its prototype (via instanceOf association)
3. Loads prototype property definitions (PropertyDefs)
4. Merges prototype properties with concept values
5. Returns a hydrated object with all properties populated

This enables JavaScript-style prototype inheritance where:
- Prototype defines the schema (properties)
- Concept provides the values
- Object automatically has all prototype properties + concept values
"""

from typing import Dict, Any, Optional, List
from src.personal_assistant.models import Node, Edge
from src.personal_assistant.tools import MemoryTools


class KSGORM:
    """
    ORM-like interface for Knowshowgo that automatically hydrates objects
    with prototype properties and concept values.
    
    Works like JavaScript prototype-based OOP:
    - Prototype defines properties (schema)
    - Concept provides values (instance data)
    - Hydrated object = prototype properties + concept values
    """
    
    def __init__(self, memory: MemoryTools):
        self.memory = memory
    
    def get_concept(self, concept_uuid: str, hydrate: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get a concept and optionally hydrate it with prototype properties.
        
        Args:
            concept_uuid: UUID of the concept to retrieve
            hydrate: If True, automatically populate with prototype properties
            
        Returns:
            Hydrated object dict with prototype properties + concept values, or None if not found
        """
        # Load concept node
        concept_node = self._get_node_by_uuid(concept_uuid)
        if not concept_node:
            return None
        
        if not hydrate:
            # Return raw concept
            return self._node_to_dict(concept_node)
        
        # Hydrate: find prototype and merge properties
        return self.hydrate_concept(concept_node)
    
    def hydrate_concept(self, concept_node: Node) -> Dict[str, Any]:
        """
        Hydrate a concept with its prototype properties.
        
        Process:
        1. Find prototype via instanceOf association
        2. Load prototype property definitions
        3. Merge prototype properties (schema) with concept values
        4. Return hydrated object
        
        Args:
            concept_node: The concept Node to hydrate
            
        Returns:
            Hydrated object dict
        """
        # Start with concept properties
        hydrated = self._node_to_dict(concept_node)
        
        # Find prototype via instanceOf association
        prototype_node = self._find_prototype(concept_node)
        if not prototype_node:
            return hydrated  # Return concept as-is if no prototype
        
        # Load prototype property definitions
        property_defs = self._load_prototype_properties(prototype_node)
        
        # Merge: prototype properties (schema) + concept values
        # Concept values override prototype defaults
        for prop_def in property_defs:
            prop_name = prop_def.get("name") or prop_def.get("propertyName")
            if not prop_name:
                continue
            
            # If concept doesn't have this property, add it from prototype (with default/undefined)
            if prop_name not in hydrated.get("props", {}):
                # Property exists in schema but not in instance
                # In JavaScript, this would be undefined
                hydrated["props"][prop_name] = None
        
        # Also load inherited prototype properties (if prototype has parent)
        parent_prototype = self._find_parent_prototype(prototype_node)
        if parent_prototype:
            parent_props = self._load_prototype_properties(parent_prototype)
            for prop_def in parent_props:
                prop_name = prop_def.get("name") or prop_def.get("propertyName")
                if prop_name and prop_name not in hydrated.get("props", {}):
                    hydrated["props"][prop_name] = None
        
        return hydrated
    
    def _find_prototype(self, concept_node: Node) -> Optional[Node]:
        """Find the prototype for a concept via instanceOf association."""
        concept_uuid = concept_node.uuid if isinstance(concept_node, Node) else concept_node.get("uuid")
        
        # Search for instanceOf edge
        if hasattr(self.memory, "edges"):
            for edge in self.memory.edges.values():
                if (edge.from_node == concept_uuid and 
                    (edge.rel == "instanceOf" or edge.props.get("p") == "instanceOf")):
                    return self._get_node_by_uuid(edge.to_node)
        
        # Fallback: check props for prototype_uuid
        props = concept_node.props if isinstance(concept_node, Node) else concept_node.get("props", {})
        prototype_uuid = props.get("prototype_uuid")
        if prototype_uuid:
            return self._get_node_by_uuid(prototype_uuid)
        
        return None
    
    def _find_parent_prototype(self, prototype_node: Node) -> Optional[Node]:
        """Find parent prototype via inherits edge."""
        prototype_uuid = prototype_node.uuid if isinstance(prototype_node, Node) else prototype_node.get("uuid")
        
        if hasattr(self.memory, "edges"):
            for edge in self.memory.edges.values():
                if (edge.from_node == prototype_uuid and 
                    edge.rel == "inherits"):
                    parent_uuid = edge.to_node
                    parent_node = self._get_node_by_uuid(parent_uuid)
                    # Only return if it's actually a prototype
                    if parent_node:
                        props = parent_node.props if isinstance(parent_node, Node) else parent_node.get("props", {})
                        if props.get("isPrototype") is True:
                            return parent_node
        
        return None
    
    def _load_prototype_properties(self, prototype_node: Node) -> List[Dict[str, Any]]:
        """
        Load PropertyDefs associated with a prototype.
        
        In Knowshowgo design, prototypes can define properties via:
        - defines_prop edges (Prototype → PropertyDef)
        - Or PropertyDefs can be searched by name matching prototype schema
        
        For now, we'll search for PropertyDefs that might be associated with this prototype.
        In a full implementation, we'd traverse defines_prop edges.
        """
        property_defs = []
        
        # Method 1: Search for defines_prop edges (if they exist)
        prototype_uuid = prototype_node.uuid if isinstance(prototype_node, Node) else prototype_node.get("uuid")
        if hasattr(self.memory, "edges"):
            for edge in self.memory.edges.values():
                if (edge.from_node == prototype_uuid and 
                    edge.rel == "defines_prop"):
                    prop_def_node = self._get_node_by_uuid(edge.to_node)
                    if prop_def_node:
                        property_defs.append(self._node_to_dict(prop_def_node))
        
        # Method 2: If no defines_prop edges, search all PropertyDefs
        # (This is a fallback - in production, defines_prop edges should be used)
        if not property_defs and hasattr(self.memory, "nodes"):
            for node in self.memory.nodes.values():
                if node.kind == "PropertyDef":
                    property_defs.append(self._node_to_dict(node))
        
        return property_defs
    
    def _get_node_by_uuid(self, node_uuid: str) -> Optional[Node]:
        """Get a node by UUID."""
        if hasattr(self.memory, "nodes"):
            return self.memory.nodes.get(node_uuid)
        
        # Fallback: search
        try:
            results = self.memory.search("", top_k=1000, filters={})
            for r in results:
                uuid_val = r.get("uuid") if isinstance(r, dict) else getattr(r, "uuid", None)
                if uuid_val == node_uuid:
                    if isinstance(r, Node):
                        return r
                    # Convert dict to Node
                    return Node(
                        kind=r.get("kind", ""),
                        labels=r.get("labels", []),
                        props=r.get("props", {}),
                        uuid=r.get("uuid"),
                        llm_embedding=r.get("llm_embedding"),
                        status=r.get("status"),
                    )
        except Exception:
            pass
        
        return None
    
    def _node_to_dict(self, node: Node) -> Dict[str, Any]:
        """Convert a Node to a dict representation."""
        if isinstance(node, dict):
            return node
        
        props = node.props if hasattr(node, "props") else {}
        label = props.get("label") or (node.labels[0] if node.labels else "")
        
        # Ensure both 'label'/'name' and 'summary'/'description' are available for backward compatibility
        hydrated_props = props.copy()
        summary = props.get("summary", "")
        
        if "name" not in hydrated_props and label:
            hydrated_props["name"] = label
        if "label" not in hydrated_props and label:
            hydrated_props["label"] = label
        
        if "description" not in hydrated_props and summary:
            hydrated_props["description"] = summary
        if "summary" not in hydrated_props and summary:
            hydrated_props["summary"] = summary
        
        return {
            "uuid": node.uuid if hasattr(node, "uuid") else None,
            "kind": node.kind if hasattr(node, "kind") else "topic",
            "label": label,
            "name": label,  # Backward compat: name = label
            "aliases": props.get("aliases", []) or node.labels,
            "summary": props.get("summary", ""),
            "isPrototype": props.get("isPrototype", False),
            "status": node.status if hasattr(node, "status") else props.get("status", "active"),
            "namespace": props.get("namespace", "public"),
            "props": hydrated_props,  # All properties (concept values) with name/label
            "prototype_properties": [],  # Will be populated during hydration
        }
    
    def query(self, query_text: str, top_k: int = 5, hydrate: bool = True) -> List[Dict[str, Any]]:
        """
        Query concepts and optionally hydrate them.
        
        Args:
            query_text: Search query
            top_k: Number of results
            hydrate: If True, hydrate each result with prototype properties
            
        Returns:
            List of hydrated concept objects
        """
        # Search for concepts
        results = self.memory.search(
            query_text,
            top_k=top_k,
            filters={"kind": "topic"},  # All nodes are topics in Knowshowgo
        )
        
        hydrated_results = []
        for result in results:
            if isinstance(result, Node):
                node = result
            elif isinstance(result, dict):
                # Convert dict to Node for processing
                node = Node(
                    kind=result.get("kind", "topic"),
                    labels=result.get("labels", []),
                    props=result.get("props", {}),
                    uuid=result.get("uuid"),
                    llm_embedding=result.get("llm_embedding"),
                    status=result.get("status"),
                )
            else:
                continue
            
            # Check if it's a concept (not a prototype)
            props = node.props if hasattr(node, "props") else {}
            if props.get("isPrototype") is True:
                continue  # Skip prototypes
            
            if hydrate:
                hydrated = self.hydrate_concept(node)
            else:
                hydrated = self._node_to_dict(node)
            
            hydrated_results.append(hydrated)
        
        return hydrated_results
    
    def create_object(self, prototype_name: str, properties: Dict[str, Any], embed_fn=None) -> Dict[str, Any]:
        """
        Create a new concept object from a prototype name and properties.
        
        Similar to JavaScript: `new Person({name: "John", email: "john@example.com"})`
        
        Args:
            prototype_name: Name of the prototype (e.g., "Person", "Procedure")
            properties: Dictionary of property names to values
            embed_fn: Optional embedding function for the concept
            
        Returns:
            Hydrated concept object
        """
        # Find prototype by name
        prototype_node = self._find_prototype_by_name(prototype_name)
        if not prototype_node:
            raise ValueError(f"Prototype '{prototype_name}' not found")
        
        # Extract label/name from properties
        label = properties.get("name") or properties.get("label") or "unnamed"
        description = properties.get("description") or properties.get("summary", "")
        
        # Create embedding if embed_fn provided
        embedding = None
        if embed_fn:
            try:
                embedding = embed_fn(f"{label} {description}")
            except Exception:
                pass
        
        # Create concept node
        from datetime import datetime, timezone
        from src.personal_assistant.models import Provenance
        
        prov = Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="ksg-orm-create",
        )
        
        concept = Node(
            kind="topic",
            labels=[label],
            props={
                "label": label,
                "summary": description,
                "isPrototype": False,
                "status": "active",
                "namespace": "public",
                "prototype_uuid": prototype_node.uuid,
                **{k: v for k, v in properties.items() if k not in ("name", "label", "description", "summary")},
            },
            llm_embedding=embedding,
        )
        
        self.memory.upsert(concept, prov, embedding_request=True)
        
        # Create instanceOf association
        from src.personal_assistant.models import Edge
        instance_edge = Edge(
            from_node=concept.uuid,
            to_node=prototype_node.uuid,
            rel="instanceOf",
            props={
                "w": 1.0,
                "status": "accepted",
            },
        )
        self.memory.upsert(instance_edge, prov, embedding_request=False)
        
        # Return hydrated object
        return self.hydrate_concept(concept)
    
    def save_object(self, hydrated_obj: Dict[str, Any], embed_fn=None) -> Dict[str, Any]:
        """
        Save a hydrated object back to the knowledge graph.
        
        Updates the concept with new property values. Similar to JavaScript object assignment.
        
        Args:
            hydrated_obj: Hydrated concept object (from get_concept_hydrated or create_object)
            embed_fn: Optional embedding function for updating embeddings
            
        Returns:
            Updated hydrated object
        """
        concept_uuid = hydrated_obj.get("uuid")
        if not concept_uuid:
            raise ValueError("Object must have a UUID to save")
        
        # Get current concept node
        concept_node = self._get_node_by_uuid(concept_uuid)
        if not concept_node:
            raise ValueError(f"Concept with UUID {concept_uuid} not found")
        
        # Update properties from hydrated_obj.props
        props = hydrated_obj.get("props", {})
        
        # Update concept node properties
        # Preserve system fields (isPrototype, namespace, prototype_uuid) but allow updates to others
        updated_props = concept_node.props.copy()
        
        # Update all properties except protected system fields
        for k, v in props.items():
            if k not in ("isPrototype", "namespace", "prototype_uuid"):
                updated_props[k] = v
        
        # Update label/summary if changed (handle both name/label and description/summary)
        if "label" in props:
            updated_props["label"] = props["label"]
        elif "name" in props:
            updated_props["label"] = props["name"]
        
        if "summary" in props:
            updated_props["summary"] = props["summary"]
        elif "description" in props:
            updated_props["summary"] = props["description"]
        
        # Update status if provided (allow status updates)
        if "status" in props:
            updated_props["status"] = props["status"]
            # Also update node.status if it exists
            if hasattr(concept_node, "status"):
                concept_node.status = props["status"]
        
        # Update concept node
        concept_node.props = updated_props
        concept_node.labels = [updated_props.get("label") or concept_node.labels[0] if concept_node.labels else "concept"]
        
        # Update embedding if embed_fn provided
        if embed_fn:
            try:
                label = updated_props.get("label", "")
                summary = updated_props.get("summary", "")
                concept_node.llm_embedding = embed_fn(f"{label} {summary}")
            except Exception:
                pass
        
        # Save to memory
        from datetime import datetime, timezone
        from src.personal_assistant.models import Provenance
        
        prov = Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="ksg-orm-save",
        )
        
        self.memory.upsert(concept_node, prov, embedding_request=True)
        
        # Return updated hydrated object
        return self.hydrate_concept(concept_node)
    
    def update_properties(self, concept_uuid: str, properties: Dict[str, Any], embed_fn=None) -> Dict[str, Any]:
        """
        Update specific properties of a concept.
        
        Similar to JavaScript: `object.property = value` or `Object.assign(object, {property: value})`
        
        Args:
            concept_uuid: UUID of the concept to update
            properties: Dictionary of property names to new values
            embed_fn: Optional embedding function for updating embeddings
            
        Returns:
            Updated hydrated object
        """
        # Get current hydrated object
        hydrated = self.get_concept(concept_uuid, hydrate=True)
        if not hydrated:
            raise ValueError(f"Concept with UUID {concept_uuid} not found")
        
        # Update properties
        hydrated["props"].update(properties)
        
        # Save and return
        return self.save_object(hydrated, embed_fn=embed_fn)
    
    def _find_prototype_by_name(self, prototype_name: str) -> Optional[Node]:
        """Find a prototype node by its name/label."""
        if hasattr(self.memory, "nodes"):
            for node in self.memory.nodes.values():
                props = node.props if hasattr(node, "props") else {}
                if (props.get("isPrototype") is True and 
                    (props.get("label") == prototype_name or 
                     props.get("name") == prototype_name or
                     prototype_name in node.labels)):
                    return node
        
        # Fallback: search
        try:
            results = self.memory.search(prototype_name, top_k=10, filters={"kind": "topic"})
            for result in results:
                if isinstance(result, Node):
                    node = result
                elif isinstance(result, dict):
                    node = Node(
                        kind=result.get("kind", "topic"),
                        labels=result.get("labels", []),
                        props=result.get("props", {}),
                        uuid=result.get("uuid"),
                        llm_embedding=result.get("llm_embedding"),
                        status=result.get("status"),
                    )
                else:
                    continue
                
                props = node.props if hasattr(node, "props") else {}
                if (props.get("isPrototype") is True and 
                    (props.get("label") == prototype_name or prototype_name in node.labels)):
                    return node
        except Exception:
            pass
        
        return None

