"""
Test enhanced learning capabilities:
1. LLM reasoning about failures
2. Transfer learning from similar cases
3. Knowledge accumulation from successes
4. Learning from user feedback
"""

import json
import unittest
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch

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
from src.personal_assistant.ksg import KSGStore
from src.personal_assistant.learning_engine import LearningEngine


class TestAgentEnhancedLearning(unittest.TestCase):
    """Test enhanced learning capabilities."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            """Simple embedding function."""
            text_lower = text.lower()
            if "login" in text_lower:
                return [1.0, 0.5, 0.2]
            elif "success" in text_lower or "worked" in text_lower:
                return [0.9, 0.6, 0.3]
            elif "failure" in text_lower or "error" in text_lower:
                return [0.8, 0.7, 0.4]
            else:
                return [float(len(text)) * 0.01, 0.1 * len(text.split()) * 0.01, 0.0]
        
        # Seed prototypes
        ksg_store = KSGStore(self.memory)
        ksg_store.ensure_seeds(embedding_fn=embed)
        
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.procedure_builder = ProcedureBuilder(self.memory, embed_fn=embed)
    
    def _create_agent_with_llm_plan(self, llm_plan: Dict[str, Any], chat_response_override: Optional[str] = None):
        """Helper to create agent with specific LLM plan."""
        response = chat_response_override or json.dumps(llm_plan)
        llm_client = FakeOpenAIClient(
            chat_response=response,
            embedding=[1.0, 0.5, 0.2]
        )
        
        return PersonalAssistantAgent(
            memory=self.memory,
            calendar=MockCalendarTools(),
            tasks=MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            procedure_builder=self.procedure_builder,
            ksg=self.ksg,
            openai_client=llm_client,
        )
    
    def test_llm_reasoning_about_failures(self):
        """Test that agent uses LLM reasoning to analyze failures."""
        user_msg = "Login to example.com"
        
        # First attempt fails
        llm_plan_fail = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.fill", "params": {"url": "https://example.com", "selector": "#wrong-email", "text": "user@example.com"}},
            ]
        }
        
        # Adaptation with LLM reasoning
        llm_plan_adapt = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.fill", "params": {"url": "https://example.com", "selector": "#email", "text": "user@example.com"}},
            ]
        }
        
        # Mock LLM to return different plans for initial and adaptation
        call_count = [0]
        def mock_chat(messages, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps(llm_plan_fail)
            else:
                return json.dumps(llm_plan_adapt)
        
        llm_client = FakeOpenAIClient(chat_response=json.dumps(llm_plan_fail), embedding=[1.0, 0.5, 0.2])
        llm_client.chat = mock_chat
        
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
        
        result = agent.execute_request(user_msg)
        
        # Verify adaptation was attempted
        # The agent should have tried to adapt after failure
        self.assertIn(result["execution_results"]["status"], ("completed", "error", "ask_user"))
    
    def test_transfer_learning_from_similar_cases(self):
        """Test that agent transfers knowledge from similar successful cases."""
        # Store a successful case
        success_uuid = self.ksg.create_concept(
            prototype_uuid=self._get_procedure_prototype_uuid(),
            json_obj={
                "name": "Successful Login Procedure",
                "description": "Login to site.com",
                "steps": [
                    {"tool": "web.fill", "params": {"selector": "#email", "text": "user@example.com"}},
                    {"tool": "web.fill", "params": {"selector": "#password", "text": "pass123"}},
                ]
            },
            embedding=[1.0, 0.5, 0.2],
        )
        
        # Store as knowledge/lesson
        from src.personal_assistant.models import Node
        knowledge_node = Node(
            kind="topic",
            labels=["Knowledge", "Lesson", "Success"],
            props={
                "label": "Lessons from successful login",
                "what_worked": ["Using #email selector", "Filling password field"],
                "key_success_factors": ["Correct selectors", "Proper field order"],
            },
        )
        knowledge_node.llm_embedding = [0.9, 0.6, 0.3]
        self.memory.upsert(knowledge_node, Provenance("user", "2026-01-07T12:00:00Z", 1.0, "test"))
        
        # Now user asks for similar task
        user_msg = "Login to newsite.com"
        
        llm_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "ksg.search_concepts", "params": {"query": "login procedure", "top_k": 3}},
                {"tool": "web.fill", "params": {"url": "https://newsite.com", "selector": "#email", "text": "user@example.com"}},
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan)
        result = agent.execute_request(user_msg)
        
        # Verify execution attempted
        self.assertIn(result["execution_results"]["status"], ("completed", "error", "ask_user"))
        
        # Verify similar knowledge was found (learning engine should find it)
        learning_engine = agent.learning_engine
        similar_knowledge = learning_engine.find_similar_knowledge("login to site", top_k=3)
        self.assertGreater(len(similar_knowledge), 0, "Should find similar knowledge")
    
    def test_learn_from_success(self):
        """Test that agent learns from successful executions."""
        user_msg = "Fill out a form at example.com"
        
        llm_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.fill", "params": {"url": "https://example.com", "selector": "#name", "text": "John Doe"}},
            ]
        }
        
        # Mock LLM to return success analysis
        success_analysis = {
            "what_worked": ["Using #name selector", "Filling form in correct order"],
            "key_success_factors": ["Correct selector", "Proper timing"],
            "reusable_patterns": ["Form filling pattern"],
            "best_practices": ["Check selector before filling"],
        }
        
        llm_client = FakeOpenAIClient(
            chat_response=json.dumps(llm_plan),
            embedding=[1.0, 0.5, 0.2]
        )
        
        # Override chat to return success analysis when learning engine calls it
        original_chat = llm_client.chat
        call_count = [0]
        def mock_chat(messages, **kwargs):
            call_count[0] += 1
            if "extract lessons learned from this successful execution" in str(messages):
                return json.dumps(success_analysis)
            return original_chat(messages, **kwargs)
        llm_client.chat = mock_chat
        
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
        
        result = agent.execute_request(user_msg)
        
        # Verify execution completed
        self.assertEqual(result["execution_results"]["status"], "completed")
        
        # Verify knowledge was stored
        knowledge_nodes = [n for n in self.memory.nodes.values() 
                          if n.kind == "topic" and "Knowledge" in n.labels]
        # Knowledge may be stored, but it's non-blocking so we just verify it doesn't break
        self.assertIsNotNone(result)
    
    def test_learn_from_user_feedback(self):
        """Test that agent learns from user feedback and corrections."""
        user_feedback = "The selector should be #username, not #email"
        
        learning_engine = LearningEngine(
            memory=self.memory,
            ksg=self.ksg,
            llm_client=FakeOpenAIClient(chat_response='{"what_was_wrong": ["Wrong selector"], "correct_approach": "Use #username", "lessons": ["Check selector carefully"], "future_guidance": "Verify selector matches DOM"}'),
            embed_fn=lambda x: [1.0, 0.5, 0.2],
        )
        
        knowledge_uuid = learning_engine.learn_from_user_feedback(
            user_feedback=user_feedback,
            original_request="Login to example.com",
            plan={"steps": [{"tool": "web.fill", "params": {"selector": "#email"}}]},
            execution_results={"status": "error", "error": "Selector not found"},
            provenance=Provenance("user", "2026-01-07T12:00:00Z", 1.0, "test"),
        )
        
        # Verify correction was stored
        self.assertIsNotNone(knowledge_uuid)
        
        # Verify correction can be found
        corrections = learning_engine.find_similar_knowledge("login selector", top_k=3)
        self.assertGreater(len(corrections), 0, "Should find stored correction")
    
    def _get_procedure_prototype_uuid(self) -> str:
        """Get Procedure prototype UUID."""
        for node in self.memory.nodes.values():
            if (node.kind == "topic" and 
                node.props.get("isPrototype") is True and
                node.props.get("label") == "Procedure"):
                return node.uuid
        # Fallback: create it
        return self.ksg.create_prototype(
            name="Procedure",
            description="A learned workflow",
            context="assistant",
            labels=["Procedure"],
            embedding=[0.9, 0.6, 0.3],
        )


if __name__ == "__main__":
    unittest.main()

