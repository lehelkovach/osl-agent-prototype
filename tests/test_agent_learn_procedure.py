"""
Test Module 1: Agent learns procedures from chat and stores in KnowShowGo.

Goal: User teaches procedure via chat → Agent stores it in KnowShowGo semantic memory.
"""
import json
import unittest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.models import Provenance
from src.personal_assistant.ontology_init import ensure_default_prototypes
from datetime import datetime, timezone


def get_procedure_prototype(memory):
    """Helper to get Procedure prototype UUID"""
    for node in memory.nodes.values():
        if node.kind == "Prototype" and node.props.get("name") == "Procedure":
            return node.uuid
    return None


class TestAgentLearnProcedure(unittest.TestCase):
    """Test that agent learns procedures from chat and stores in KnowShowGo"""

    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            # Simple embedding function for testing
            return [float(len(text)), 0.1 * len(text.split())]
        
        # Seed prototypes
        ensure_default_prototypes(self.memory, embed, trace_id="learn-test")
        
        self.proc_proto_uuid = get_procedure_prototype(self.memory)
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.procedure_builder = ProcedureBuilder(self.memory, embed_fn=embed)

    def test_user_teaches_procedure_stored_in_ksg(self):
        """Test: User teaches procedure via chat, agent stores it in KnowShowGo"""
        # Arrange: Mock LLM to return plan that creates a concept
        procedure_steps = [
            {"tool": "web.get", "params": {"url": "https://example.com/login"}},
            {"tool": "web.fill", "params": {"selectors": {"email": "input[type='email']", "password": "input[type='password']"}}},
            {"tool": "web.click_selector", "params": {"selector": "button[type='submit']"}},
        ]
        
        llm_plan = {
            "intent": "task",
            "steps": [{
                "tool": "ksg.create_concept",
                "params": {
                    "prototype_uuid": self.proc_proto_uuid,
                    "json_obj": {
                        "name": "Login Procedure",
                        "description": "Procedure for logging into a website",
                        "steps": procedure_steps
                    },
                    "embedding": [1.0, 0.5]  # Mock embedding
                }
            }]
        }
        
        llm_client = FakeOpenAIClient(
            chat_response=json.dumps(llm_plan),
            embedding=[0.1, 0.2]
        )
        
        agent = PersonalAssistantAgent(
            memory=self.memory,
            calendar=MockCalendarTools(),
            tasks=MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            procedure_builder=self.procedure_builder,
            ksg=self.ksg,
            openai_client=llm_client,
        )
        
        # Act: User teaches procedure
        user_msg = "Remember: to log into a site, go to the login URL, fill email and password, then click submit"
        result = agent.execute_request(user_msg)
        
        # Assert: Concept stored in KnowShowGo
        concepts = [n for n in self.memory.nodes.values() if n.kind == "Concept"]
        self.assertGreater(len(concepts), 0, "Concept should be stored")
        
        # Find the stored concept
        stored_concept = None
        for concept in concepts:
            if concept.props.get("name") == "Login Procedure":
                stored_concept = concept
                break
        
        self.assertIsNotNone(stored_concept, "Login Procedure concept should be stored")
        self.assertEqual(stored_concept.props["name"], "Login Procedure")
        self.assertIn("steps", stored_concept.props)
        self.assertEqual(len(stored_concept.props["steps"]), 3)

    def test_procedure_stored_with_embedding(self):
        """Test: Procedure stored with embedding for fuzzy matching"""
        # Arrange
        embedding = [1.0, 0.5, 0.3]
        
        concept_uuid = self.ksg.create_concept(
            prototype_uuid=self.proc_proto_uuid,
            json_obj={
                "name": "Test Procedure",
                "description": "Test procedure",
                "steps": []
            },
            embedding=embedding,
        )
        
        # Assert
        concept = self.memory.nodes[concept_uuid]
        self.assertEqual(concept.llm_embedding, embedding, "Concept should store embedding")
        self.assertIsNotNone(concept.llm_embedding, "Embedding should not be None")

    def test_procedure_steps_stored_correctly(self):
        """Test: Procedure steps stored correctly in concept"""
        # Arrange
        steps = [
            {"tool": "web.get", "params": {"url": "https://example.com"}},
            {"tool": "web.fill", "params": {"selectors": {"field": "input"}}},
            {"tool": "web.click_selector", "params": {"selector": "button"}},
        ]
        
        concept_uuid = self.ksg.create_concept(
            prototype_uuid=self.proc_proto_uuid,
            json_obj={
                "name": "Procedure with Steps",
                "steps": steps
            },
            embedding=[1.0, 0.5],
        )
        
        # Assert
        concept = self.memory.nodes[concept_uuid]
        stored_steps = concept.props.get("steps", [])
        self.assertEqual(len(stored_steps), 3, "All steps should be stored")
        self.assertEqual(stored_steps[0]["tool"], "web.get")
        self.assertEqual(stored_steps[1]["tool"], "web.fill")
        self.assertEqual(stored_steps[2]["tool"], "web.click_selector")

    def test_concept_instantiates_prototype(self):
        """Test: Stored concept has instantiates edge to prototype"""
        # Arrange
        concept_uuid = self.ksg.create_concept(
            prototype_uuid=self.proc_proto_uuid,
            json_obj={"name": "Test Procedure"},
            embedding=[1.0, 0.5],
        )
        
        # Assert: Edge exists
        inst_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == concept_uuid and e.rel == "instantiates"
        ]
        self.assertEqual(len(inst_edges), 1, "Concept should instantiate prototype")
        self.assertEqual(inst_edges[0].to_node, self.proc_proto_uuid)


if __name__ == "__main__":
    unittest.main()

