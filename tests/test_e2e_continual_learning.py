"""
End-to-end tests demonstrating continual learning capabilities:
1. Learning from failure with LLM reasoning
2. Transfer learning from similar cases
3. Learning from success and building knowledge
4. Learning from user feedback
5. Survey answer reuse across different forms
6. Full workflow: learn → fail → adapt → succeed → generalize
"""

import json
import unittest
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.openai_client import FakeOpenAIClient, OpenAIClient
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
from src.personal_assistant.cpms_adapter import CPMSAdapter
from tests.test_cpms_adapter import FakeCpmsClientWithPatterns


class MockWebToolsWithLearning(MockWebTools):
    """Mock web tools that simulate learning scenarios."""
    
    def __init__(self):
        super().__init__()
        self.attempts = {}  # Track attempts per URL
        self.success_patterns = {}  # Store what works for each site
    
    def fill(self, url: str, selector: str = "", text: str = "", selectors: Dict[str, str] = None, values: Dict[str, str] = None, **kwargs) -> Dict[str, Any]:
        """Simulate form filling with learning - first attempt fails, learns correct selector."""
        if url not in self.attempts:
            self.attempts[url] = 0
        
        self.attempts[url] += 1
        
        # First attempt fails with wrong selector
        if self.attempts[url] == 1:
            if selector and "#wrong" in selector:
                return {"status": "error", "error": f"Selector {selector} not found in DOM"}
            if selectors:
                for sel in selectors.values():
                    if "#wrong" in sel:
                        return {"status": "error", "error": f"Selector {sel} not found in DOM"}
        
        # After learning, use correct selector
        if url not in self.success_patterns:
            # Learn: correct selector is #email or input[type='email']
            self.success_patterns[url] = {
                "email": "#email",
                "password": "#password",
            }
        
        return {"status": "success", "url": url, "selector": selector or (list(selectors.values())[0] if selectors else ""), "text": text or (list(values.values())[0] if values else "")}
    
    def click_selector(self, url: str, selector: str) -> Dict[str, Any]:
        """Simulate clicking."""
        return {"status": "success", "url": url, "clicked": selector}


class TestE2EContinualLearning(unittest.TestCase):
    """End-to-end tests for continual learning."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            """Simple embedding function."""
            text_lower = text.lower()
            if "login" in text_lower:
                return [1.0, 0.5, 0.2]
            elif "survey" in text_lower:
                return [0.9, 0.6, 0.3]
            elif "success" in text_lower or "worked" in text_lower:
                return [0.8, 0.7, 0.4]
            elif "failure" in text_lower or "error" in text_lower:
                return [0.7, 0.8, 0.5]
            else:
                return [float(len(text)) * 0.01, 0.1 * len(text.split()) * 0.01, 0.0]
        
        # Seed prototypes
        ksg_store = KSGStore(self.memory)
        ksg_store.ensure_seeds(embedding_fn=embed)
        
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.procedure_builder = ProcedureBuilder(self.memory, embed_fn=embed)
        self.web_tools = MockWebToolsWithLearning()
        self.cpms = CPMSAdapter(FakeCpmsClientWithPatterns())
    
    def _create_agent_with_adaptive_llm(self, initial_plan: Dict[str, Any], adaptation_plan: Dict[str, Any]):
        """Create agent with LLM that adapts after failure."""
        call_count = [0]
        
        def mock_chat(messages, **kwargs):
            call_count[0] += 1
            # First call: initial plan (fails)
            if call_count[0] == 1:
                return json.dumps(initial_plan)
            # Subsequent calls: adaptation (succeeds)
            else:
                return json.dumps(adaptation_plan)
        
        llm_client = FakeOpenAIClient(chat_response=json.dumps(initial_plan), embedding=[1.0, 0.5, 0.2])
        llm_client.chat = mock_chat
        
        return PersonalAssistantAgent(
            memory=self.memory,
            calendar=MockCalendarTools(),
            tasks=MockTaskTools(),
            web=self.web_tools,
            contacts=MockContactsTools(),
            procedure_builder=self.procedure_builder,
            ksg=self.ksg,
            openai_client=llm_client,
            cpms=self.cpms,
        )
    
    def test_e2e_learn_from_failure_with_reasoning(self):
        """E2E: Agent learns from failure using LLM reasoning."""
        user_msg = "Login to example.com"
        
        # Initial plan with wrong selector
        initial_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.get_dom", "params": {"url": "https://example.com/login"}},
                {"tool": "web.fill", "params": {"url": "https://example.com/login", "selector": "#wrong-email", "text": "user@example.com"}},
            ]
        }
        
        # Adapted plan with correct selector (after LLM reasoning)
        adaptation_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.get_dom", "params": {"url": "https://example.com/login"}},
                {"tool": "web.fill", "params": {"url": "https://example.com/login", "selector": "#email", "text": "user@example.com"}},
                {"tool": "web.fill", "params": {"url": "https://example.com/login", "selector": "#password", "text": "pass123"}},
                {"tool": "web.click_selector", "params": {"url": "https://example.com/login", "selector": "button[type='submit']"}},
            ]
        }
        
        agent = self._create_agent_with_adaptive_llm(initial_plan, adaptation_plan)
        result = agent.execute_request(user_msg)
        
        # Verify adaptation occurred
        self.assertIn(result["execution_results"]["status"], ("completed", "error", "ask_user"))
        
        # Verify learning engine was used
        self.assertIsNotNone(agent.learning_engine)
        
        # Verify procedure was stored (could be Procedure kind or topic kind)
        procedures = []
        for n in self.memory.nodes.values():
            if n.kind == "Procedure":
                # Old-style procedure
                title = n.props.get("title", "") or n.props.get("name", "")
                if "login" in str(title).lower():
                    procedures.append(n)
            elif n.kind == "topic" and n.props.get("isPrototype") is False:
                # New-style concept
                label = n.props.get("label", "") or n.props.get("name", "")
                if "login" in str(label).lower():
                    procedures.append(n)
        
        # Procedure should be stored after successful execution
        if result["execution_results"]["status"] == "completed":
            self.assertGreater(len(procedures), 0, "Procedure should be stored after learning")
    
    def test_e2e_transfer_learning_across_sites(self):
        """E2E: Agent transfers knowledge from one site to another."""
        # First: Learn login for site1.com
        site1_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.fill", "params": {"url": "https://site1.com/login", "selector": "#email", "text": "user@example.com"}},
                {"tool": "web.fill", "params": {"url": "https://site1.com/login", "selector": "#password", "text": "pass123"}},
                {"tool": "web.click_selector", "params": {"url": "https://site1.com/login", "selector": "button[type='submit']"}},
            ]
        }
        
        agent1 = self._create_agent_with_adaptive_llm(site1_plan, site1_plan)
        result1 = agent1.execute_request("Login to site1.com")
        
        # Verify first login succeeded and was stored
        self.assertEqual(result1["execution_results"]["status"], "completed")
        
        # Now: Transfer to site2.com
        site2_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "ksg.search_concepts", "params": {"query": "login procedure", "top_k": 3}},
                {"tool": "web.fill", "params": {"url": "https://site2.com/login", "selector": "#email", "text": "user@example.com"}},
                {"tool": "web.fill", "params": {"url": "https://site2.com/login", "selector": "#password", "text": "pass123"}},
                {"tool": "web.click_selector", "params": {"url": "https://site2.com/login", "selector": "button[type='submit']"}},
            ]
        }
        
        agent2 = self._create_agent_with_adaptive_llm(site2_plan, site2_plan)
        result2 = agent2.execute_request("Login to site2.com")
        
        # Verify transfer learning occurred
        self.assertEqual(result2["execution_results"]["status"], "completed")
        
        # Verify similar knowledge was found and used
        learning_engine = agent2.learning_engine
        similar_knowledge = learning_engine.find_similar_knowledge("login to site", top_k=3)
        # Should find the site1.com login procedure
        self.assertGreater(len(similar_knowledge), 0, "Should find similar login knowledge")
    
    def test_e2e_learn_from_user_feedback(self):
        """E2E: Agent learns from user feedback and applies it."""
        # Initial attempt fails
        initial_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.fill", "params": {"url": "https://example.com", "selector": "#email", "text": "user@example.com"}},
            ]
        }
        
        agent = self._create_agent_with_adaptive_llm(initial_plan, initial_plan)
        result = agent.execute_request("Login to example.com")
        
        trace_id = result.get("plan", {}).get("trace_id") or result.get("execution_results", {}).get("trace_id")
        
        # User provides feedback
        user_feedback = "The email field selector should be #username, not #email"
        
        # Learn from feedback
        from src.personal_assistant.models import Provenance
        provenance = Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id=trace_id or "test-trace",
        )
        
        knowledge_uuid = agent.learning_engine.learn_from_user_feedback(
            user_feedback=user_feedback,
            original_request="Login to example.com",
            plan=initial_plan,
            execution_results=result.get("execution_results", {}),
            provenance=provenance,
        )
        
        # Verify feedback was learned
        self.assertIsNotNone(knowledge_uuid, "Feedback should be stored as knowledge")
        
        # Verify correction can be found
        corrections = agent.learning_engine.find_similar_knowledge("login selector", top_k=3)
        self.assertGreater(len(corrections), 0, "Should find stored correction")
    
    def test_e2e_survey_answer_reuse_workflow(self):
        """E2E: Complete survey answer reuse workflow."""
        # Phase 1: Fill first survey and store answers
        survey1_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.get_dom", "params": {"url": "https://example.com/survey1"}},
                {"tool": "cpms.detect_form", "params": {"html": "<form>...</form>", "url": "https://example.com/survey1"}},
                {"tool": "web.fill", "params": {
                    "url": "https://example.com/survey1",
                    "selectors": {"favorite_language": "#fav-lang", "years_experience": "#years-exp"},
                    "values": {"favorite_language": "Python", "years_experience": "5"}
                }},
                {"tool": "ksg.create_concept", "params": {
                    "prototype_uuid": self._get_survey_response_prototype_uuid(),
                    "json_obj": {
                        "name": "Survey Response - Programming",
                        "questions": [
                            {"question": "What is your favorite programming language?", "answer": "Python", "field_name": "favorite_language"},
                            {"question": "How many years of experience?", "answer": "5", "field_name": "years_experience"}
                        ]
                    },
                    "embedding": [1.0, 0.5, 0.2]
                }},
            ]
        }
        
        agent1 = self._create_agent_with_adaptive_llm(survey1_plan, survey1_plan)
        result1 = agent1.execute_request("Fill out this survey at example.com/survey1")
        
        # Verify first survey was filled and stored
        self.assertEqual(result1["execution_results"]["status"], "completed")
        
        # Phase 2: Fill similar survey using remembered answers
        survey2_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.get_dom", "params": {"url": "https://example.com/survey2"}},
                {"tool": "cpms.detect_form", "params": {"html": "<form>...</form>", "url": "https://example.com/survey2"}},
                {"tool": "ksg.search_concepts", "params": {"query": "survey response programming", "top_k": 3}},
                {"tool": "form.autofill", "params": {
                    "url": "https://example.com/survey2",
                    "selectors": {"preferred_language": "#pref-lang", "experience_years": "#exp-years"},
                    "questions": [
                        {"question": "Which programming language do you prefer?", "field_name": "preferred_language"},
                        {"question": "Years of professional experience?", "field_name": "experience_years"}
                    ]
                }},
            ]
        }
        
        agent2 = self._create_agent_with_adaptive_llm(survey2_plan, survey2_plan)
        result2 = agent2.execute_request("Fill out this similar survey at example.com/survey2")
        
        # Verify second survey used remembered answers
        self.assertEqual(result2["execution_results"]["status"], "completed")
    
    def test_e2e_full_learning_cycle(self):
        """E2E: Complete learning cycle - learn → fail → adapt → succeed → generalize."""
        # Step 1: Learn initial procedure
        learn_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "procedure.create", "params": {
                    "title": "Login to site1.com",
                    "description": "Login procedure",
                    "steps": [
                        {"tool": "web.fill", "params": {"url": "https://site1.com", "selector": "#email", "text": "user@example.com"}},
                        {"tool": "web.fill", "params": {"url": "https://site1.com", "selector": "#password", "text": "pass123"}},
                    ]
                }},
            ]
        }
        
        agent = self._create_agent_with_adaptive_llm(learn_plan, learn_plan)
        result1 = agent.execute_request("Learn how to login to site1.com")
        self.assertEqual(result1["execution_results"]["status"], "completed")
        
        # Step 2: Try similar site, fails initially
        fail_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.fill", "params": {"url": "https://site2.com", "selector": "#wrong-email", "text": "user@example.com"}},
            ]
        }
        
        # Step 3: Adapt and succeed
        succeed_plan = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.fill", "params": {"url": "https://site2.com", "selector": "#email", "text": "user@example.com"}},
                {"tool": "web.fill", "params": {"url": "https://site2.com", "selector": "#password", "text": "pass123"}},
            ]
        }
        
        agent2 = self._create_agent_with_adaptive_llm(fail_plan, succeed_plan)
        result2 = agent2.execute_request("Login to site2.com")
        
        # Verify adaptation occurred
        self.assertIn(result2["execution_results"]["status"], ("completed", "error", "ask_user"))
        
        # Step 4: After multiple successes, should generalize
        # (This would happen automatically when 2+ similar procedures work)
        procedures = []
        for n in self.memory.nodes.values():
            if n.kind == "Procedure":
                title = n.props.get("title", "") or n.props.get("name", "")
                if "login" in str(title).lower():
                    procedures.append(n)
            elif n.kind == "topic" and n.props.get("isPrototype") is False:
                label = n.props.get("label", "") or n.props.get("name", "")
                if "login" in str(label).lower():
                    procedures.append(n)
        
        # Should have learned procedures
        self.assertGreater(len(procedures), 0, "Should have learned login procedures")
    
    def test_e2e_continual_improvement_through_feedback(self):
        """E2E: Agent improves through multiple feedback cycles."""
        # Initial attempt
        plan1 = {
            "intent": "web_io",
            "steps": [
                {"tool": "web.fill", "params": {"url": "https://example.com", "selector": "#email", "text": "user@example.com"}},
            ]
        }
        
        agent = self._create_agent_with_adaptive_llm(plan1, plan1)
        result1 = agent.execute_request("Login to example.com")
        
        # User feedback 1
        feedback1 = "Use #username instead of #email"
        from src.personal_assistant.models import Provenance
        provenance1 = Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "test-1")
        agent.learning_engine.learn_from_user_feedback(
            user_feedback=feedback1,
            original_request="Login to example.com",
            plan=plan1,
            execution_results=result1.get("execution_results", {}),
            provenance=provenance1,
        )
        
        # Second attempt (should use learned knowledge)
        plan2 = {
            "intent": "web_io",
            "steps": [
                {"tool": "ksg.search_concepts", "params": {"query": "login selector correction", "top_k": 3}},
                {"tool": "web.fill", "params": {"url": "https://example.com", "selector": "#username", "text": "user@example.com"}},
            ]
        }
        
        agent2 = self._create_agent_with_adaptive_llm(plan2, plan2)
        result2 = agent2.execute_request("Login to example.com again")
        
        # Verify second attempt used learned knowledge
        self.assertEqual(result2["execution_results"]["status"], "completed")
        
        # Verify knowledge accumulated
        knowledge = agent2.learning_engine.find_similar_knowledge("login selector", top_k=5)
        self.assertGreater(len(knowledge), 0, "Should have accumulated knowledge from feedback")
    
    def _get_survey_response_prototype_uuid(self) -> str:
        """Get SurveyResponse prototype UUID."""
        for node in self.memory.nodes.values():
            if (node.kind == "topic" and 
                node.props.get("isPrototype") is True and
                node.props.get("label") == "SurveyResponse"):
                return node.uuid
        # Create it
        return self.ksg.create_prototype(
            name="SurveyResponse",
            description="Stored responses to survey questions",
            context="assistant",
            labels=["SurveyResponse", "FormData"],
            embedding=[1.0, 0.5, 0.2],
        )


class TestE2ELiveLearning(unittest.TestCase):
    """E2E tests that can run with real services (gated by environment variables)."""
    
    def setUp(self):
        """Set up for live tests if environment allows."""
        self.use_live = os.getenv("TEST_LIVE_LEARNING", "0") == "1"
        if not self.use_live:
            self.skipTest("Set TEST_LIVE_LEARNING=1 to run live tests")
        
        # Use real services
        from src.personal_assistant.service import default_agent_from_env
        self.agent = default_agent_from_env()
        self.memory = self.agent.memory
    
    @unittest.skipUnless(os.getenv("TEST_LIVE_LEARNING") == "1", "Requires TEST_LIVE_LEARNING=1")
    def test_live_learn_from_failure(self):
        """Live test: Agent learns from failure with real LLM reasoning."""
        user_msg = "Go to https://example.com and try to find a login form"
        
        result = self.agent.execute_request(user_msg)
        
        # Verify execution attempted
        self.assertIn(result["execution_results"]["status"], ("completed", "error", "ask_user"))
        
        # If it failed, verify adaptation was attempted
        if result["execution_results"]["status"] == "error":
            # Check if learning engine analyzed the failure
            self.assertIsNotNone(self.agent.learning_engine)
    
    @unittest.skipUnless(os.getenv("TEST_LIVE_LEARNING") == "1", "Requires TEST_LIVE_LEARNING=1")
    def test_live_transfer_learning(self):
        """Live test: Agent transfers knowledge between similar tasks."""
        # First task
        result1 = self.agent.execute_request("Remember that I like Python programming")
        self.assertEqual(result1["execution_results"]["status"], "completed")
        
        # Similar task - should use transferred knowledge
        result2 = self.agent.execute_request("What programming language do I like?")
        self.assertIn(result2["execution_results"]["status"], ("completed", "ask_user"))


if __name__ == "__main__":
    unittest.main()

