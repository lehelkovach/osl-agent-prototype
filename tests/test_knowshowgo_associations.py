import unittest
from datetime import datetime, timezone

from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Provenance
from src.personal_assistant.ontology_init import ensure_default_prototypes


class TestKnowShowGoAssociations(unittest.TestCase):
    """Test KnowShowGo API associations and object properties"""

    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            return [float(len(text)), 0.1]
        
        ensure_default_prototypes(self.memory, embed, trace_id="assoc-test")
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.prov = Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "assoc-test")
        
        # Find Object prototype
        self.object_proto = None
        for node in self.memory.nodes.values():
            if node.kind == "Prototype" and node.props.get("name") == "Object":
                self.object_proto = node
                break
        
        # Create test concepts
        self.concept1_uuid = self.ksg.create_concept(
            prototype_uuid=self.object_proto.uuid if self.object_proto else "unknown",
            json_obj={"name": "TestConcept1", "description": "First concept"},
            embedding=[1.0, 0.0],
            provenance=self.prov
        )
        self.concept2_uuid = self.ksg.create_concept(
            prototype_uuid=self.object_proto.uuid if self.object_proto else "unknown",
            json_obj={"name": "TestConcept2", "description": "Second concept"},
            embedding=[0.0, 1.0],
            provenance=self.prov
        )

    def test_add_association_different_types(self):
        """Test creating associations with different relationship types"""
        # Test "has_a" association with explicit strength (fuzzy ontology)
        has_a_edge_uuid = self.ksg.add_association(
            from_concept_uuid=self.concept1_uuid,
            to_concept_uuid=self.concept2_uuid,
            relation_type="has_a",
            strength=0.9,  # Fuzzy relationship strength
            provenance=self.prov
        )
        
        # Test "uses" association
        uses_edge_uuid = self.ksg.add_association(
            from_concept_uuid=self.concept1_uuid,
            to_concept_uuid=self.concept2_uuid,
            relation_type="uses",
            props={"frequency": 5},
            provenance=self.prov
        )
        
        # Test "depends_on" association
        depends_edge_uuid = self.ksg.add_association(
            from_concept_uuid=self.concept1_uuid,
            to_concept_uuid=self.concept2_uuid,
            relation_type="depends_on",
            provenance=self.prov
        )
        
        # Verify edges were created
        edges = list(self.memory.edges.values())
        edge_rels = {e.rel for e in edges if e.from_node == self.concept1_uuid and e.to_node == self.concept2_uuid}
        
        self.assertIn("has_a", edge_rels)
        self.assertIn("uses", edge_rels)
        self.assertIn("depends_on", edge_rels)
        
        # Verify fuzzy relationship strength is stored
        has_a_edge = [e for e in edges if e.uuid == has_a_edge_uuid][0]
        self.assertEqual(has_a_edge.props.get("strength"), 0.9, "Fuzzy relationship strength should be stored")
        
        # Verify default strength is 1.0
        default_edge_uuid = self.ksg.add_association(
            from_concept_uuid=self.concept1_uuid,
            to_concept_uuid=self.concept2_uuid,
            relation_type="default_test",
            provenance=self.prov
        )
        default_edge = [e for e in self.memory.edges.values() if e.uuid == default_edge_uuid][0]
        self.assertEqual(default_edge.props.get("strength"), 1.0, "Default strength should be 1.0")
        
        uses_edge = [e for e in edges if e.uuid == uses_edge_uuid][0]
        self.assertEqual(uses_edge.props.get("frequency"), 5)

    def test_create_object_with_properties(self):
        """Test creating an object with properties creates concepts and has_a edges"""
        properties = {
            "email": "user@example.com",
            "name": "John Doe",
            "age": 30
        }
        
        result = self.ksg.create_object_with_properties(
            object_name="UserObject",
            object_kind="Agent",
            properties=properties,
            prototype_uuid=self.object_proto.uuid if self.object_proto else None,
            provenance=self.prov
        )
        
        object_uuid = result["object_uuid"]
        
        # Verify object concept was created
        self.assertIn(object_uuid, self.memory.nodes)
        object_concept = self.memory.nodes[object_uuid]
        self.assertEqual(object_concept.kind, "Concept")
        self.assertEqual(object_concept.props["name"], "UserObject")
        self.assertEqual(object_concept.props["kind"], "Agent")
        
        # Verify properties are in object concept props
        # Note: "name" property conflicts with object_name, so object_name takes precedence
        for prop_name, prop_value in properties.items():
            if prop_name == "name":
                # Skip "name" property check since object_name takes precedence
                # The object_name "UserObject" is already verified above
                continue
            self.assertEqual(object_concept.props[prop_name], prop_value)
        
        # Verify has_a edges were created
        has_a_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == object_uuid and e.rel == "has_a"
        ]
        self.assertEqual(len(has_a_edges), len(properties), "Should have has_a edge for each property")
        
        # Verify property definitions or property concepts exist
        self.assertEqual(len(result["property_uuids"]), len(properties))
        
        # Verify ObjectProperty nodes were created
        self.assertEqual(len(result["object_property_uuids"]), len(properties))
        for obj_prop_uuid in result["object_property_uuids"]:
            self.assertIn(obj_prop_uuid, self.memory.nodes)
            obj_prop = self.memory.nodes[obj_prop_uuid]
            self.assertEqual(obj_prop.kind, "ObjectProperty")
            self.assertIn("property_name", obj_prop.props)
            self.assertIn("property_value", obj_prop.props)
        
        # Verify has_property edges were created
        has_prop_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == object_uuid and e.rel == "has_property"
        ]
        self.assertEqual(len(has_prop_edges), len(properties), "Should have has_property edge for each property")

    def test_object_properties_store_values(self):
        """Test that ObjectProperty nodes store the actual property values"""
        properties = {
            "email": "test@example.com",
            "role": "admin"
        }
        
        result = self.ksg.create_object_with_properties(
            object_name="TestUser",
            object_kind="Agent",
            properties=properties,
            provenance=self.prov
        )
        
        # Verify ObjectProperty nodes have correct values
        for obj_prop_uuid in result["object_property_uuids"]:
            obj_prop = self.memory.nodes[obj_prop_uuid]
            prop_name = obj_prop.props["property_name"]
            prop_value = obj_prop.props["property_value"]
            self.assertEqual(prop_value, properties[prop_name])
            self.assertEqual(obj_prop.props["object_uuid"], result["object_uuid"])

    def test_association_with_self(self):
        """Test that associations can be created (even with self, though unusual)"""
        edge_uuid = self.ksg.add_association(
            from_concept_uuid=self.concept1_uuid,
            to_concept_uuid=self.concept1_uuid,
            relation_type="self_reference",
            provenance=self.prov
        )
        
        edges = [e for e in self.memory.edges.values() if e.uuid == edge_uuid]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].rel, "self_reference")

    def test_association_properties_preserved(self):
        """Test that association edge properties are preserved"""
        custom_props = {
            "created_at": "2024-01-01",
            "confidence": 0.95,
            "metadata": {"source": "user_input"}
        }
        
        edge_uuid = self.ksg.add_association(
            from_concept_uuid=self.concept1_uuid,
            to_concept_uuid=self.concept2_uuid,
            relation_type="custom_relation",
            props=custom_props,
            provenance=self.prov
        )
        
        edge = [e for e in self.memory.edges.values() if e.uuid == edge_uuid][0]
        self.assertEqual(edge.props["created_at"], "2024-01-01")
        self.assertEqual(edge.props["confidence"], 0.95)
        self.assertEqual(edge.props["metadata"], {"source": "user_input"})


if __name__ == "__main__":
    unittest.main()

