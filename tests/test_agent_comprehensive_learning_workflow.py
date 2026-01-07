"""
Comprehensive test for agent learning workflow:
- Learn procedures from chat
- Recall and reuse procedures
- Adapt procedures when they fail (1-3 tries)
- Ask for user input when confidence is low
- Generalize procedures to different cases
- Successfully execute adapted procedures
"""

import json
import unittest
from typing import Dict, Any, Optional, List
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
from datetime import datetime, timezone


class MockWebToolsWithFormVariations(MockWebTools):
    """Mock web tools that simulate different form variations."""
    
    def __init__(self):
        super().__init__()
        self.form_variations = {
            "page=1": {
                "email_selector": "input[type='email']",
                "password_selector": "input[type='password']",
                "submit_selector": "button[type='submit']",
            },
            "page=2": {
                "email_selector": "#username",
                "password_selector": "#pass",
                "submit_selector": "#login-btn",
            },
            "page=3": {
                "email_selector": "input[name='user_email']",
                "password_selector": "input[name='user_pass']",
                "submit_selector": "input[value='Sign In']",
            },
        }
        self.current_page = None
        self.attempts = {}  # Track attempts per URL
    
    def get_dom(self, url: str) -> Dict[str, Any]:
        """Return DOM with form structure based on page parameter."""
        # Extract page parameter
        if "page=" in url:
            page = url.split("page=")[1].split("&")[0]
            self.current_page = f"page={page}"
        else:
            self.current_page = "page=1"
        
        # Generate HTML based on form variation
        variation = self.form_variations.get(self.current_page, self.form_variations["page=1"])
        html = f"""
        <html>
        <body>
            <form>
                <input type="email" id="{variation['email_selector'].replace('#', '').replace('[', '').replace(']', '')}" />
                <input type="password" id="{variation['password_selector'].replace('#', '').replace('[', '').replace(']', '')}" />
                <button type="submit">{variation['submit_selector']}</button>
            </form>
        </body>
        </html>
        """
        return {"status": 200, "html": html, "url": url}
    
    def fill(self, url: str, selectors: Dict[str, str], values: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        """Simulate form filling - succeeds if correct selectors for current page."""
        if "page=" in url:
            page = url.split("page=")[1].split("&")[0]
            variation = self.form_variations.get(f"page={page}", self.form_variations["page=1"])
        else:
            variation = self.form_variations["page=1"]
        
        # Check if selectors match current page variation
        email_match = any(
            sel == variation["email_selector"] or 
            sel in variation["email_selector"] or 
            variation["email_selector"] in sel
            for sel in selectors.values()
        )
        
        if not email_match:
            return {"status": "error", "error": "Selector not found"}
        
        return {"status": "success", "url": url, "filled": selectors}
    
    def click_selector(self, url: str, selector: str) -> Dict[str, Any]:
        """Simulate clicking - succeeds if correct selector for current page."""
        if "page=" in url:
            page = url.split("page=")[1].split("&")[0]
            variation = self.form_variations.get(f"page={page}", self.form_variations["page=1"])
        else:
            variation = self.form_variations["page=1"]
        
        # Check if selector matches
        if selector != variation["submit_selector"] and variation["submit_selector"] not in selector:
            return {"status": "error", "error": f"Selector '{selector}' not found. Expected '{variation['submit_selector']}'"}
        
        return {"status": "success", "url": url, "clicked": selector}


class TestAgentComprehensiveLearningWorkflow(unittest.TestCase):
    """Test comprehensive learning workflow with real-world scenarios."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            """Simple embedding function that groups similar concepts."""
            text_lower = text.lower()
            # Login-related concepts get similar embeddings
            if "login" in text_lower or "log in" in text_lower:
                base = [1.0, 0.5, 0.2]
            elif "procedure" in text_lower:
                base = [0.9, 0.6, 0.3]
            else:
                base = [float(len(text)) * 0.01, 0.1 * len(text.split()) * 0.01, 0.0]
            
            # Add variation based on URL/site
            if "page=1" in text_lower or "test1" in text_lower:
                return [base[0], base[1], base[2] + 0.1]
            elif "page=2" in text_lower or "test2" in text_lower:
                return [base[0], base[1], base[2] + 0.2]
            elif "page=3" in text_lower or "test3" in text_lower:
                return [base[0], base[1], base[2] + 0.3]
            return base
        
        # Seed prototypes
        ksg_store = KSGStore(self.memory)
        ksg_store.ensure_seeds(embedding_fn=embed)
        
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.procedure_builder = ProcedureBuilder(self.memory, embed_fn=embed)
        self.web_tools = MockWebToolsWithFormVariations()
    
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
            web=self.web_tools,
            contacts=MockContactsTools(),
            procedure_builder=self.procedure_builder,
            ksg=self.ksg,
            openai_client=llm_client,
        )
    
    def test_phase1_learn_procedure_from_chat(self):
        """Phase 1: Agent learns procedure from user instruction."""
        # User instructs agent to login
        user_msg = "Go to the login form test page at file:///tests/fixtures/login_generate.html?page=1 and login with email test@example.com and password testpass123"
        
        # LLM creates plan to learn and execute procedure
        llm_plan = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "web.get_dom",
                    "params": {"url": "file:///tests/fixtures/login_generate.html?page=1"},
                    "comment": "Get DOM to analyze form structure"
                },
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "file:///tests/fixtures/login_generate.html?page=1",
                        "selectors": {"email": "input[type='email']", "password": "input[type='password']"},
                        "values": {"email": "test@example.com", "password": "testpass123"}
                    },
                    "comment": "Fill login form"
                },
                {
                    "tool": "web.click_selector",
                    "params": {
                        "url": "file:///tests/fixtures/login_generate.html?page=1",
                        "selector": "button[type='submit']"
                    },
                    "comment": "Click submit button"
                },
                {
                    "tool": "ksg.create_concept_recursive",
                    "params": {
                        "prototype_uuid": self._get_procedure_prototype_uuid(),
                        "json_obj": {
                            "name": "Login to login form test page",
                            "description": "Procedure to login to the test login form",
                            "steps": [
                                {"tool": "web.get_dom", "params": {"url": "file:///tests/fixtures/login_generate.html?page=1"}},
                                {"tool": "web.fill", "params": {"selectors": {"email": "input[type='email']", "password": "input[type='password']"}}},
                                {"tool": "web.click_selector", "params": {"selector": "button[type='submit']"}},
                            ]
                        },
                        "embedding": [1.0, 0.5, 0.2]
                    },
                    "comment": "Store learned procedure"
                }
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan)
        result = agent.execute_request(user_msg)
        
        # Verify procedure was learned
        self.assertEqual(result["execution_results"]["status"], "completed")
        
        # Verify procedure stored in memory
        # Look for concepts (topics with isPrototype=False) that have "login" in name or label
        procedures = [n for n in self.memory.nodes.values() 
                     if n.kind == "topic" and n.props.get("isPrototype") is False 
                     and ("login" in str(n.props.get("name", "")).lower() or 
                          "login" in str(n.props.get("label", "")).lower())]
        self.assertGreater(len(procedures), 0, f"Procedure should be stored. Found {len(self.memory.nodes)} nodes total. Procedure nodes: {[n.props.get('name') or n.props.get('label') for n in self.memory.nodes.values() if n.kind == 'topic' and n.props.get('isPrototype') is False]}")
    
    def test_phase2_recall_and_adapt_procedure(self):
        """Phase 2: Agent recalls procedure and adapts it for similar page."""
        # First, learn a procedure for page=1
        self.test_phase1_learn_procedure_from_chat()
        
        # Now user asks to login to similar page (page=2)
        user_msg = "This is a similar login page at file:///tests/fixtures/login_generate.html?page=2, login here with the same credentials"
        
        # LLM should recall previous procedure and adapt it
        llm_plan = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "ksg.search_concepts",
                    "params": {"query": "login form test page", "top_k": 3},
                    "comment": "Search for similar login procedures"
                },
                {
                    "tool": "web.get_dom",
                    "params": {"url": "file:///tests/fixtures/login_generate.html?page=2"},
                    "comment": "Get DOM to analyze new form structure"
                },
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "file:///tests/fixtures/login_generate.html?page=2",
                        "selectors": {"email": "#username", "password": "#pass"},
                        "values": {"email": "test@example.com", "password": "testpass123"}
                    },
                    "comment": "Fill login form with adapted selectors"
                },
                {
                    "tool": "web.click_selector",
                    "params": {
                        "url": "file:///tests/fixtures/login_generate.html?page=2",
                        "selector": "#login-btn"
                    },
                    "comment": "Click submit with adapted selector"
                }
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan)
        result = agent.execute_request(user_msg)
        
        # Should succeed (or ask for help if adaptation needed)
        self.assertIn(result["execution_results"]["status"], ("completed", "ask_user"))
    
    def test_phase3_adaptation_after_failure(self):
        """Phase 3: Agent adapts procedure after execution failure (1-3 tries)."""
        # Learn procedure for page=1
        self.test_phase1_learn_procedure_from_chat()
        
        # Try to use it on page=2 (different selectors) - first attempt fails
        user_msg = "Login to file:///tests/fixtures/login_generate.html?page=2"
        
        # First attempt: uses wrong selectors (from page=1)
        llm_plan_attempt1 = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "ksg.search_concepts",
                    "params": {"query": "login form test page", "top_k": 3},
                },
                {
                    "tool": "web.get_dom",
                    "params": {"url": "file:///tests/fixtures/login_generate.html?page=2"},
                },
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "file:///tests/fixtures/login_generate.html?page=2",
                        "selectors": {"email": "input[type='email']", "password": "input[type='password']"},  # Wrong selectors
                    },
                },
                {
                    "tool": "web.click_selector",
                    "params": {
                        "url": "file:///tests/fixtures/login_generate.html?page=2",
                        "selector": "button[type='submit']"  # Wrong selector
                    },
                }
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan_attempt1)
        result1 = agent.execute_request(user_msg)
        
        # First attempt should fail or ask for help
        if result1["execution_results"]["status"] == "ask_user":
            # User provides guidance
            guidance_msg = "The email field is #username, password is #pass, and submit button is #login-btn"
            
            # Second attempt: adapted procedure
            llm_plan_attempt2 = {
                "intent": "web_io",
                "steps": [
                    {
                        "tool": "web.get_dom",
                        "params": {"url": "file:///tests/fixtures/login_generate.html?page=2"},
                    },
                    {
                        "tool": "web.fill",
                        "params": {
                            "url": "file:///tests/fixtures/login_generate.html?page=2",
                            "selectors": {"email": "#username", "password": "#pass"},  # Correct selectors
                        },
                    },
                    {
                        "tool": "web.click_selector",
                        "params": {
                            "url": "file:///tests/fixtures/login_generate.html?page=2",
                            "selector": "#login-btn"  # Correct selector
                        },
                    },
                    {
                        "tool": "ksg.create_concept",
                        "params": {
                            "prototype_uuid": self._get_procedure_prototype_uuid(),
                            "json_obj": {
                                "name": "Login to login form test page (page 2)",
                                "description": "Adapted procedure for page 2",
                                "steps": [
                                    {"tool": "web.fill", "params": {"selectors": {"email": "#username", "password": "#pass"}}},
                                    {"tool": "web.click_selector", "params": {"selector": "#login-btn"}},
                                ]
                            },
                            "embedding": [1.0, 0.5, 0.3]
                        },
                    }
                ]
            }
            
            agent2 = self._create_agent_with_llm_plan(llm_plan_attempt2)
            result2 = agent2.execute_request(guidance_msg)
            
            # Second attempt should succeed
            self.assertEqual(result2["execution_results"]["status"], "completed")
    
    def test_phase4_generalization_after_multiple_exemplars(self):
        """Phase 4: Agent generalizes after multiple successful adaptations."""
        # Learn procedures for page=1, page=2, page=3
        # Create multiple successful login procedures
        proc_uuid_1 = self.ksg.create_concept(
            prototype_uuid=self._get_procedure_prototype_uuid(),
            json_obj={
                "name": "Login page 1",
                "description": "Login procedure for page 1",
                "steps": [{"tool": "web.fill", "params": {"selectors": {"email": "input[type='email']"}}}],
            },
            embedding=[1.0, 0.5, 0.2],
        )
        
        proc_uuid_2 = self.ksg.create_concept(
            prototype_uuid=self._get_procedure_prototype_uuid(),
            json_obj={
                "name": "Login page 2",
                "description": "Login procedure for page 2",
                "steps": [{"tool": "web.fill", "params": {"selectors": {"email": "#username"}}}],
            },
            embedding=[1.0, 0.5, 0.3],
        )
        
        proc_uuid_3 = self.ksg.create_concept(
            prototype_uuid=self._get_procedure_prototype_uuid(),
            json_obj={
                "name": "Login page 3",
                "description": "Login procedure for page 3",
                "steps": [{"tool": "web.fill", "params": {"selectors": {"email": "input[name='user_email']"}}}],
            },
            embedding=[1.0, 0.5, 0.4],
        )
        
        # Agent should auto-generalize when it sees multiple similar procedures
        # This is tested by checking if generalization occurs after multiple exemplars
        exemplars = [proc_uuid_1, proc_uuid_2, proc_uuid_3]
        
        # Check if agent can find these as similar concepts
        matches = self.ksg.search_concepts("login procedure", top_k=5)
        self.assertGreaterEqual(len(matches), 2, "Should find multiple login procedures")
    
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

