"""Tests for Selector Adaptation (Milestone C).

Tests verify:
- Fallback selector trial on fill failure
- Winning selector persistence to stored procedure
- Run outcome tracking (success_count, failure_count)
"""
import json
import unittest
from datetime import datetime, timezone
from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.models import Node, Provenance


class SelectiveWebTools:
    """Web tools that fail on specific selectors."""
    
    def __init__(self, fail_selectors: list = None):
        self.fail_selectors = fail_selectors or []
        self.history = []
        self.fill_attempts = []
    
    def fill(self, url: str, selector: str, text: str):
        self.fill_attempts.append({"url": url, "selector": selector, "text": text})
        if selector in self.fail_selectors:
            raise RuntimeError(f"Selector {selector} not found")
        res = {"status": 200, "url": url, "selector": selector, "text": text}
        self.history.append(res)
        return res
    
    def get(self, **kwargs):
        return {"status": 200}
    
    def post(self, **kwargs):
        return {"status": 200}
    
    def screenshot(self, **kwargs):
        return {"status": 200}
    
    def get_dom(self, **kwargs):
        return {"status": 200, "html": "<html><body></body></html>"}
    
    def locate_bounding_box(self, **kwargs):
        return {"status": 200}
    
    def click_selector(self, **kwargs):
        return {"status": 200}
    
    def click_xpath(self, **kwargs):
        return {"status": 200}
    
    def click_xy(self, **kwargs):
        return {"status": 200}
    
    def wait_for(self, **kwargs):
        return {"status": 200}


class TestSelectorFallback(unittest.TestCase):
    """Test fallback selector behavior."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.calendar = MockCalendarTools()
        self.tasks = MockTaskTools()
        self.prov = Provenance(source="user", ts="now", confidence=1.0, trace_id="test")
    
    def test_email_fallback_selectors_are_tried(self):
        """When #email fails, fallback selectors like input[type='email'] are tried."""
        web = SelectiveWebTools(fail_selectors=["#email"])
        
        plan = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "http://example.com",
                        "selectors": {"email": "#email"},
                        "values": {"email": "test@example.com"},
                    },
                }
            ],
        }
        
        agent = PersonalAssistantAgent(
            self.memory,
            self.calendar,
            self.tasks,
            web=web,
            openai_client=FakeOpenAIClient(
                chat_response=json.dumps(plan),
                embedding=[0.1, 0.2]
            ),
        )
        
        result = agent.execute_request("Fill email form")
        
        # Should have tried fallback selectors
        self.assertGreater(len(web.fill_attempts), 1)
        # First attempt was the failed selector
        self.assertEqual(web.fill_attempts[0]["selector"], "#email")
        # Subsequent attempts were fallbacks
        fallback_selectors = [a["selector"] for a in web.fill_attempts[1:]]
        self.assertTrue(any(s.startswith("input[") for s in fallback_selectors))
    
    def test_password_fallback_selectors_are_tried(self):
        """When #password fails, fallback selectors are tried."""
        web = SelectiveWebTools(fail_selectors=["#password"])
        
        plan = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "http://example.com",
                        "selectors": {"password": "#password"},
                        "values": {"password": "secret123"},
                    },
                }
            ],
        }
        
        agent = PersonalAssistantAgent(
            self.memory,
            self.calendar,
            self.tasks,
            web=web,
            openai_client=FakeOpenAIClient(
                chat_response=json.dumps(plan),
                embedding=[0.1, 0.2]
            ),
        )
        
        agent.execute_request("Fill password")
        
        # Should have tried password-specific fallbacks
        selectors_tried = [a["selector"] for a in web.fill_attempts]
        self.assertIn("#password", selectors_tried)
        # Should have tried input[type='password']
        self.assertTrue(
            any("password" in s for s in selectors_tried if s != "#password")
        )


class TestRunOutcomeTracking(unittest.TestCase):
    """Test that run outcomes are tracked (success_count, failure_count)."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.calendar = MockCalendarTools()
        self.tasks = MockTaskTools()
        self.builder = ProcedureBuilder(self.memory, embed_fn=lambda t: [0.1, 0.2])
        self.prov = Provenance(source="user", ts="now", confidence=1.0, trace_id="test")
    
    def test_successful_run_increments_success_count(self):
        """Successful execution increments success_count."""
        web = SelectiveWebTools()  # No failures
        
        # Create a procedure
        proc = self.builder.create_procedure(
            title="Success Test",
            description="Test success tracking",
            steps=[
                {
                    "title": "get",
                    "tool": "web.get",
                    "payload": {"tool": "web.get", "params": {"url": "http://test.com"}},
                }
            ],
            provenance=self.prov,
        )
        
        plan = {
            "intent": "web_io",
            "procedure_uuid": proc["procedure_uuid"],
            "steps": [
                {"tool": "web.get", "params": {"url": "http://test.com"}}
            ],
        }
        
        agent = PersonalAssistantAgent(
            self.memory,
            self.calendar,
            self.tasks,
            web=web,
            procedure_builder=self.builder,
            openai_client=FakeOpenAIClient(
                chat_response=json.dumps(plan),
                embedding=[0.1, 0.2]
            ),
        )
        
        # Execute
        agent.execute_request("Run success test")
        
        # Check procedure was updated
        proc_node = self.memory.nodes.get(proc["procedure_uuid"])
        self.assertIsNotNone(proc_node)
        self.assertEqual(proc_node.props.get("success_count"), 1)
        self.assertEqual(proc_node.props.get("failure_count"), 0)
    
    def test_multiple_runs_accumulate_counts(self):
        """Multiple runs accumulate success/failure counts."""
        web = SelectiveWebTools()
        
        proc = self.builder.create_procedure(
            title="Multi Run Test",
            description="Test multiple runs",
            steps=[
                {
                    "title": "get",
                    "tool": "web.get",
                    "payload": {"tool": "web.get", "params": {"url": "http://test.com"}},
                }
            ],
            provenance=self.prov,
        )
        
        plan = {
            "intent": "web_io",
            "procedure_uuid": proc["procedure_uuid"],
            "steps": [
                {"tool": "web.get", "params": {"url": "http://test.com"}}
            ],
        }
        
        agent = PersonalAssistantAgent(
            self.memory,
            self.calendar,
            self.tasks,
            web=web,
            procedure_builder=self.builder,
            openai_client=FakeOpenAIClient(
                chat_response=json.dumps(plan),
                embedding=[0.1, 0.2]
            ),
        )
        
        # Run twice
        agent.execute_request("Run test 1")
        agent.execute_request("Run test 2")
        
        # Check counts
        proc_node = self.memory.nodes.get(proc["procedure_uuid"])
        self.assertEqual(proc_node.props.get("success_count"), 2)


class TestSelectorPersistence(unittest.TestCase):
    """Test that winning selectors are persisted back to procedures."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.calendar = MockCalendarTools()
        self.tasks = MockTaskTools()
        self.builder = ProcedureBuilder(self.memory, embed_fn=lambda t: [0.1, 0.2])
        self.prov = Provenance(source="user", ts="now", confidence=1.0, trace_id="test")
    
    def test_winning_selector_persisted_to_step(self):
        """Fallback selector that works is persisted to the stored step."""
        # Fail on #bad-selector, succeed on fallbacks
        web = SelectiveWebTools(fail_selectors=["#bad-selector"])
        
        proc = self.builder.create_procedure(
            title="Selector Update Test",
            description="Test selector persistence",
            steps=[
                {
                    "title": "fill",
                    "tool": "web.fill",
                    "payload": {
                        "tool": "web.fill",
                        "params": {
                            "url": "http://test.com",
                            "selectors": {"email": "#bad-selector"},
                            "values": {"email": "test@example.com"},
                        },
                    },
                }
            ],
            provenance=self.prov,
        )
        
        plan = {
            "intent": "web_io",
            "procedure_uuid": proc["procedure_uuid"],
            "steps": [
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "http://test.com",
                        "selectors": {"email": "#bad-selector"},
                        "values": {"email": "test@example.com"},
                    },
                }
            ],
        }
        
        agent = PersonalAssistantAgent(
            self.memory,
            self.calendar,
            self.tasks,
            web=web,
            procedure_builder=self.builder,
            openai_client=FakeOpenAIClient(
                chat_response=json.dumps(plan),
                embedding=[0.1, 0.2]
            ),
        )
        
        result = agent.execute_request("Fill form")
        
        # Find the step and check selector was updated
        steps = self.memory.search("", top_k=10, filters={"kind": "Step"})
        proc_steps = [s for s in steps if s.get("props", {}).get("procedure_uuid") == proc["procedure_uuid"]]
        
        self.assertEqual(len(proc_steps), 1)
        step = proc_steps[0]
        updated_selectors = step.get("props", {}).get("payload", {}).get("params", {}).get("selectors", {})
        
        # Selector should have been updated from #bad-selector to a working one
        self.assertNotEqual(updated_selectors.get("email"), "#bad-selector")


if __name__ == "__main__":
    unittest.main()
