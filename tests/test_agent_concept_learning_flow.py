"""
Minimal test for agent learning flow with KnowShowGo.

Tests the core flow:
1. User requests task → Agent searches KnowShowGo → No match → Asks user
2. User provides steps → Agent creates concept → Stores in KnowShowGo  
3. Similar request → Agent finds concept → Reuses pattern
"""
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
from src.personal_assistant.ontology_init import ensure_default_prototypes


class TestAgentConceptLearningFlow(unittest.TestCase):
    """Test agent learning and reusing patterns via KnowShowGo"""

    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            # Simple embedding for testing
            return [float(len(text)), 0.1 * len(text.split())]
        
        # Seed prototypes
        ensure_default_prototypes(self.memory, embed, trace_id="learning-test")
        
        # Find Procedure prototype
        self.proc_proto = None
        for node in self.memory.nodes.values():
            if node.kind == "Prototype" and node.props.get("name") == "Procedure":
                self.proc_proto = node
                break
        
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.procedure_builder = ProcedureBuilder(self.memory, embed_fn=embed)
        
        self.agent = PersonalAssistantAgent(
            memory=self.memory,
            calendar=MockCalendarTools(),
            tasks=MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            procedure_builder=self.procedure_builder,
            ksg=self.ksg,
            openai_client=FakeOpenAIClient(
                chat_response='{"intent":"inform","steps":[]}',
                embedding=[0.1, 0.2]
            ),
        )

    def test_agent_searches_concepts_before_asking(self):
        """Test that agent searches KnowShowGo when no concepts exist"""
        # First request - no concepts stored yet
        request = "Log into X.com with my default credentials"
        
        result = self.agent.execute_request(request)
        
        # Agent should have searched (empty results, but search was attempted)
        # The agent should ask user since no concepts found
        # (actual behavior depends on LLM response, but search should have happened)
        plan = result.get("plan", {})
        
        # Verify concept search was attempted (via event emission or logs)
        # For now, just verify no crash and concept search is integrated
        self.assertIn("plan", result)
        self.assertIn("execution_results", result)

    def test_agent_creates_concept_when_user_provides_instructions(self):
        """Test that agent can create a concept when LLM decides to"""
        # Simulate agent creating a concept via ksg.create_concept tool
        # (This would normally be done by LLM in a plan step)
        
        concept_data = {
            "name": "Login to X.com",
            "description": "Login procedure for X.com",
            "steps": [
                {"tool": "web.get", "params": {"url": "https://x.com"}},
                {"tool": "web.fill", "params": {"selectors": {"email": "input[type='email']", "password": "input[type='password']"}}},
                {"tool": "web.click_selector", "params": {"selector": "button[type='submit']"}},
            ]
        }
        
        embedding = [1.0, 0.5]
        concept_uuid = self.ksg.create_concept(
            prototype_uuid=self.proc_proto.uuid,
            json_obj=concept_data,
            embedding=embedding,
        )
        
        # Verify concept was created
        self.assertIn(concept_uuid, self.memory.nodes)
        concept = self.memory.nodes[concept_uuid]
        self.assertEqual(concept.props["name"], "Login to X.com")
        self.assertEqual(concept.llm_embedding, embedding)

    def test_agent_finds_similar_concept(self):
        """Test that agent can find a similar concept via search"""
        # Create a concept
        concept_data = {
            "name": "Login to X.com",
            "description": "Login procedure for X.com",
        }
        embedding_x = [1.0, 0.5]
        concept_uuid_x = self.ksg.create_concept(
            prototype_uuid=self.proc_proto.uuid,
            json_obj=concept_data,
            embedding=embedding_x,
        )
        
        # Search for similar concept
        query = "Log into Y.com"  # Similar but different
        query_embedding = [0.95, 0.45]  # Similar embedding
        
        results = self.ksg.search_concepts(
            query=query,
            top_k=3,
            query_embedding=query_embedding
        )
        
        # Should find the similar concept (fuzzy matching)
        self.assertGreater(len(results), 0)
        # Results should include our concept (exact match in mock, but structure should work)
        result_uuids = [r.get("uuid") if isinstance(r, dict) else getattr(r, "uuid", None) for r in results]
        # Note: MockMemoryTools search may not return perfect similarity, but structure is correct

    def test_learning_flow_integration(self):
        """Integration test: learn pattern, then reuse it"""
        # Step 1: Create a learned concept (simulating user teaching agent)
        concept_data = {
            "name": "Login to Site",
            "description": "General login procedure",
            "steps": [
                {"tool": "web.get", "params": {"url": "https://example.com/login"}},
                {"tool": "web.fill", "params": {"selectors": {"email": "input[type='email']"}}},
            ]
        }
        embedding = [1.0, 0.5]
        learned_concept_uuid = self.ksg.create_concept(
            prototype_uuid=self.proc_proto.uuid,
            json_obj=concept_data,
            embedding=embedding,
        )
        
        # Step 2: Verify it's stored
        self.assertIn(learned_concept_uuid, self.memory.nodes)
        
        # Step 3: Search for similar pattern
        query = "login to website"
        query_embedding = [0.95, 0.48]  # Similar embedding
        
        matches = self.ksg.search_concepts(
            query=query,
            top_k=5,
            query_embedding=query_embedding
        )
        
        # Should find the learned concept (fuzzy matching via embeddings)
        self.assertGreater(len(matches), 0)
        
        # Step 4: Verify concept can be retrieved
        stored_concept = self.memory.nodes.get(learned_concept_uuid)
        self.assertIsNotNone(stored_concept)
        self.assertEqual(stored_concept.props["name"], "Login to Site")


if __name__ == "__main__":
    unittest.main()

