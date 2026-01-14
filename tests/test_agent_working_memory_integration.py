"""Tests for Working Memory Integration in Agent (Salvage Step D)."""
import unittest
from unittest.mock import MagicMock, patch
from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools, MockCalendarTools, MockTaskTools, MockWebTools
)
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.models import Provenance


class TestAgentWorkingMemoryIntegration(unittest.TestCase):
    """Test working memory integration in agent."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.calendar = MockCalendarTools()
        self.tasks = MockTaskTools()
        self.fake_openai = FakeOpenAIClient(
            chat_response='{"intent": "task", "steps": []}',
            embedding=[0.1, 0.2, 0.3]
        )
        self.agent = PersonalAssistantAgent(
            memory=self.memory,
            calendar=self.calendar,
            tasks=self.tasks,
            openai_client=self.fake_openai,
        )
    
    def test_agent_has_working_memory(self):
        """Agent should have working memory initialized."""
        self.assertIsNotNone(self.agent.working_memory)
        self.assertEqual(self.agent.working_memory.reinforce_delta, 1.0)
        self.assertEqual(self.agent.working_memory.max_weight, 100.0)
    
    def test_boost_by_activation_adds_boost_field(self):
        """_boost_by_activation should add _activation_boost to results."""
        # Create some test results
        results = [
            {"uuid": "uuid-1", "score": 0.8},
            {"uuid": "uuid-2", "score": 0.6},
        ]
        
        # Add activation to uuid-1
        self.agent.working_memory.link("query", "uuid-1", seed_weight=5.0)
        
        # Apply boost
        boosted = self.agent._boost_by_activation(results)
        
        # Check results have boost fields
        self.assertIn("_activation_boost", boosted[0])
        self.assertIn("_boosted_score", boosted[0])
        
        # uuid-1 should have higher boost
        uuid1_result = next(r for r in boosted if r["uuid"] == "uuid-1")
        uuid2_result = next(r for r in boosted if r["uuid"] == "uuid-2")
        self.assertGreater(uuid1_result["_activation_boost"], uuid2_result["_activation_boost"])
    
    def test_boost_by_activation_reorders_results(self):
        """_boost_by_activation should reorder by boosted score."""
        results = [
            {"uuid": "uuid-1", "score": 0.8},
            {"uuid": "uuid-2", "score": 0.6},
        ]
        
        # Give uuid-2 more activation to make it rank higher
        self.agent.working_memory.link("query", "uuid-2", seed_weight=50.0)
        
        boosted = self.agent._boost_by_activation(results)
        
        # uuid-2 should be first now due to high activation
        self.assertEqual(boosted[0]["uuid"], "uuid-2")
    
    def test_reinforce_selection_creates_link(self):
        """_reinforce_selection should create working memory link."""
        self.agent._reinforce_selection("query-1", "selected-1", seed_weight=3.0)
        
        weight = self.agent.working_memory.get_weight("query-1", "selected-1")
        self.assertEqual(weight, 3.0)
    
    def test_reinforce_selection_strengthens_existing_link(self):
        """_reinforce_selection should strengthen existing links."""
        self.agent._reinforce_selection("query-1", "selected-1", seed_weight=3.0)
        self.agent._reinforce_selection("query-1", "selected-1", seed_weight=3.0)
        
        weight = self.agent.working_memory.get_weight("query-1", "selected-1")
        self.assertEqual(weight, 4.0)  # 3.0 + 1.0 (reinforce_delta)
    
    def test_get_activated_concepts(self):
        """_get_activated_concepts should return top activated."""
        self.agent.working_memory.link("query", "concept-1", seed_weight=10.0)
        self.agent.working_memory.link("query", "concept-2", seed_weight=5.0)
        
        top = self.agent._get_activated_concepts(top_k=2)
        
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0][0], "concept-1")  # Highest first
        self.assertEqual(top[0][1], 10.0)
    
    def test_empty_results_not_affected_by_boost(self):
        """_boost_by_activation should handle empty results."""
        results = self.agent._boost_by_activation([])
        self.assertEqual(results, [])
    
    def test_results_without_uuid_not_boosted(self):
        """Results without uuid should get default boost."""
        results = [{"name": "test", "score": 0.5}]
        
        boosted = self.agent._boost_by_activation(results)
        
        self.assertEqual(boosted[0]["_activation_boost"], 0.0)


class TestDeterministicParserIntegration(unittest.TestCase):
    """Test deterministic parser integration in agent."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.calendar = MockCalendarTools()
        self.tasks = MockTaskTools()
        self.fake_openai = FakeOpenAIClient(
            chat_response='{"intent": "task", "steps": []}',
            embedding=[0.1, 0.2, 0.3]
        )
        self.agent = PersonalAssistantAgent(
            memory=self.memory,
            calendar=self.calendar,
            tasks=self.tasks,
            openai_client=self.fake_openai,
        )
    
    def test_classify_intent_with_fallback_default_off(self):
        """By default, skip_llm_for_obvious should be False."""
        self.assertFalse(self.agent.skip_llm_for_obvious)
    
    @patch.dict('os.environ', {'SKIP_LLM_FOR_OBVIOUS_INTENTS': '1'})
    def test_classify_intent_with_fallback_env_enabled(self):
        """With env flag, skip_llm should be True."""
        agent = PersonalAssistantAgent(
            memory=self.memory,
            calendar=self.calendar,
            tasks=self.tasks,
            openai_client=self.fake_openai,
        )
        self.assertTrue(agent.skip_llm_for_obvious)
    
    def test_classify_intent_with_fallback_calls_llm(self):
        """Without skip flag, should call _classify_intent."""
        with patch.object(self.agent, '_classify_intent', return_value='task') as mock:
            result = self.agent._classify_intent_with_fallback("create a file")
            mock.assert_called_once_with("create a file")
            self.assertEqual(result, "task")


class TestWorkingMemoryEnvConfig(unittest.TestCase):
    """Test working memory environment configuration."""
    
    @patch.dict('os.environ', {
        'WORKING_MEMORY_REINFORCE_DELTA': '2.5',
        'WORKING_MEMORY_MAX_WEIGHT': '50.0'
    })
    def test_working_memory_env_config(self):
        """Working memory should use env config."""
        fake_openai = FakeOpenAIClient(
            chat_response='{"intent": "task", "steps": []}',
            embedding=[0.1, 0.2, 0.3]
        )
        agent = PersonalAssistantAgent(
            memory=MockMemoryTools(),
            calendar=MockCalendarTools(),
            tasks=MockTaskTools(),
            openai_client=fake_openai,
        )
        self.assertEqual(agent.working_memory.reinforce_delta, 2.5)
        self.assertEqual(agent.working_memory.max_weight, 50.0)


if __name__ == "__main__":
    unittest.main()
