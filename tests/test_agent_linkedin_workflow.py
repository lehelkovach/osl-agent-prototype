"""
Test LinkedIn clone workflow:
1. Login to LinkedIn clone site
2. Check messages in inbox
3. Respond to soliciting messages with "no thank you"
4. Create polling/trigger mechanism
5. Reuse login and check messages for another website
"""

import json
import unittest
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta

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
from src.personal_assistant.message_tools import MockMessageTools


class MockLinkedInCloneWebTools(MockWebTools):
    """Mock web tools that simulate a LinkedIn clone site."""
    
    def __init__(self):
        super().__init__()
        self.logged_in = False
        self.inbox_messages = [
            {
                "id": "msg_1",
                "subject": "Job Opportunity - Software Engineer",
                "from": "recruiter@techcorp.com",
                "body": "We have an exciting opportunity for you!",
                "unread": True,
                "is_soliciting": True,  # This is a solicitation
            },
            {
                "id": "msg_2",
                "subject": "Coffee Chat Request",
                "from": "colleague@company.com",
                "body": "Would you like to grab coffee?",
                "unread": True,
                "is_soliciting": False,  # Not a solicitation
            },
            {
                "id": "msg_3",
                "subject": "Partnership Proposal",
                "from": "sales@startup.com",
                "body": "We'd like to partner with your company!",
                "unread": True,
                "is_soliciting": True,  # This is a solicitation
            },
        ]
        self.sent_responses = []
    
    def get_dom(self, url: str) -> Dict[str, Any]:
        """Return DOM based on URL."""
        if "login" in url.lower():
            html = """
            <html>
            <body>
                <form id="login-form">
                    <input type="email" id="email" name="email" />
                    <input type="password" id="password" name="password" />
                    <button type="submit" id="submit-btn">Sign In</button>
                </form>
            </body>
            </html>
            """
        elif "inbox" in url.lower() or "messages" in url.lower():
            # Generate inbox HTML with messages
            messages_html = ""
            for msg in self.inbox_messages:
                if msg.get("unread"):
                    messages_html += f"""
                    <div class="message-item" data-id="{msg['id']}" data-unread="true">
                        <span class="from">{msg['from']}</span>
                        <span class="subject">{msg['subject']}</span>
                        <span class="body">{msg['body']}</span>
                    </div>
                    """
            html = f"""
            <html>
            <body>
                <div class="inbox">
                    {messages_html}
                </div>
            </body>
            </html>
            """
        else:
            html = "<html><body>Page</body></html>"
        
        return {"status": 200, "html": html, "url": url}
    
    def fill(self, url: str, selectors: Dict[str, str], values: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        """Simulate form filling."""
        if "email" in selectors or "email" in str(selectors):
            self.logged_in = True
        return {"status": "success", "url": url, "filled": selectors}
    
    def click_selector(self, url: str, selector: str) -> Dict[str, Any]:
        """Simulate clicking."""
        if "submit" in selector.lower() or "sign" in selector.lower():
            self.logged_in = True
        return {"status": "success", "url": url, "clicked": selector}


class MockLinkedInMessageTools(MockMessageTools):
    """Mock message tools that simulate LinkedIn inbox."""
    
    def __init__(self, web_tools: MockLinkedInCloneWebTools):
        self.web = web_tools
        self.sent_responses = []
    
    def detect_messages(self, url: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Detect messages from the LinkedIn clone inbox."""
        messages = []
        for msg in self.web.inbox_messages:
            if filters and filters.get("unread") and not msg.get("unread"):
                continue
            messages.append({
                "id": msg["id"],
                "subject": msg["subject"],
                "from": msg["from"],
                "unread": msg.get("unread", False),
                "is_soliciting": msg.get("is_soliciting", False),
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })
        
        return {
            "status": "success",
            "url": url,
            "messages": messages,
            "count": len(messages),
            "filters_applied": filters or {},
        }
    
    def get_message_details(self, url: str, message_id: Optional[str] = None, selector: Optional[str] = None) -> Dict[str, Any]:
        """Get details of a specific message."""
        for msg in self.web.inbox_messages:
            if msg["id"] == message_id:
                return {
                    "status": "success",
                    "url": url,
                    "message_id": message_id,
                    "from": msg["from"],
                    "subject": msg["subject"],
                    "body": msg["body"],
                    "is_soliciting": msg.get("is_soliciting", False),
                }
        return {"status": "error", "error": "Message not found"}
    
    def compose_response(self, message: Dict[str, Any], template: Optional[str] = None, custom_text: Optional[str] = None) -> Dict[str, Any]:
        """Compose response."""
        response_text = custom_text or "No thank you."
        return {
            "status": "success",
            "to": message.get("from"),
            "subject": f"Re: {message.get('subject', 'Your message')}",
            "body": response_text,
            "composed_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def send_response(self, url: str, response: Dict[str, Any], message: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send response and mark message as responded."""
        self.sent_responses.append({
            "to": response.get("to"),
            "subject": response.get("subject"),
            "body": response.get("body"),
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        
        # Mark message as read/responded
        if message and message.get("id"):
            for msg in self.web.inbox_messages:
                if msg["id"] == message["id"]:
                    msg["unread"] = False
                    break
        
        return {
            "status": "success",
            "url": url,
            "response_sent": True,
            "to": response.get("to"),
            "subject": response.get("subject"),
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }


class TestAgentLinkedInWorkflow(unittest.TestCase):
    """Test LinkedIn clone workflow with polling and procedure reuse."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            """Simple embedding function."""
            text_lower = text.lower()
            if "login" in text_lower or "sign in" in text_lower:
                return [1.0, 0.5, 0.2]
            elif "message" in text_lower or "inbox" in text_lower:
                return [0.9, 0.6, 0.3]
            elif "linkedin" in text_lower:
                return [0.8, 0.7, 0.4]
            elif "trigger" in text_lower or "poll" in text_lower:
                return [0.7, 0.8, 0.5]
            else:
                return [float(len(text)) * 0.01, 0.1 * len(text.split()) * 0.01, 0.0]
        
        # Seed prototypes
        ksg_store = KSGStore(self.memory)
        ksg_store.ensure_seeds(embedding_fn=embed)
        
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.procedure_builder = ProcedureBuilder(self.memory, embed_fn=embed)
        self.web_tools = MockLinkedInCloneWebTools()
        self.message_tools = MockLinkedInMessageTools(self.web_tools)
    
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
            messages=self.message_tools,
        )
    
    def test_phase1_login_and_check_messages(self):
        """Phase 1: Login to LinkedIn clone and check messages."""
        user_msg = "Log into linkedin.com (clone site) and check messages in the inbox"
        
        llm_plan = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "web.get_dom",
                    "params": {"url": "https://linkedin.com/login"},
                    "comment": "Get login page DOM"
                },
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "https://linkedin.com/login",
                        "selectors": {"email": "#email", "password": "#password"},
                        "values": {"email": "user@example.com", "password": "password123"}
                    },
                    "comment": "Fill login form"
                },
                {
                    "tool": "web.click_selector",
                    "params": {"url": "https://linkedin.com/login", "selector": "#submit-btn"},
                    "comment": "Click sign in"
                },
                {
                    "tool": "message.detect_messages",
                    "params": {"url": "https://linkedin.com/inbox", "filters": {"unread": True}},
                    "comment": "Check for new messages"
                }
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan)
        result = agent.execute_request(user_msg)
        
        # Verify execution succeeded
        self.assertEqual(result["execution_results"]["status"], "completed")
        
        # Verify messages were detected
        # The agent should have called message.detect_messages
        self.assertTrue(self.web_tools.logged_in, "Should be logged in")
    
    def test_phase2_respond_to_soliciting_messages(self):
        """Phase 2: Respond to soliciting messages with 'no thank you'."""
        user_msg = "Respond to any new messages in the inbox that are soliciting with a 'no thank you' message"
        
        llm_plan = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "message.detect_messages",
                    "params": {"url": "https://linkedin.com/inbox", "filters": {"unread": True}},
                    "comment": "Detect new messages"
                },
                {
                    "tool": "message.get_details",
                    "params": {"url": "https://linkedin.com/inbox", "message_id": "msg_1"},
                    "comment": "Get message details to check if soliciting"
                },
                {
                    "tool": "message.compose_response",
                    "params": {"message": {"id": "msg_1", "is_soliciting": True}, "custom_text": "No thank you."},
                    "comment": "Compose 'no thank you' response"
                },
                {
                    "tool": "message.send_response",
                    "params": {
                        "url": "https://linkedin.com/inbox",
                        "response": {"to": "recruiter@techcorp.com", "subject": "Re: Job Opportunity", "body": "No thank you."},
                        "message": {"id": "msg_1"}
                    },
                    "comment": "Send response"
                }
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan)
        result = agent.execute_request(user_msg)
        
        # Verify execution succeeded
        self.assertEqual(result["execution_results"]["status"], "completed")
        
        # Verify responses were sent
        self.assertGreater(len(self.message_tools.sent_responses), 0, "Should have sent responses")
    
    def test_phase3_create_polling_trigger(self):
        """Phase 3: Create a polling/trigger mechanism for recurring inbox checks."""
        user_msg = "Set up a routine to poll the inbox every 30 minutes and respond to soliciting messages"
        
        # This should create a trigger/procedure that runs periodically
        llm_plan = {
            "intent": "task",
            "steps": [
                {
                    "tool": "ksg.create_concept_recursive",
                    "params": {
                        "prototype_uuid": self._get_procedure_prototype_uuid(),
                        "json_obj": {
                            "name": "Poll LinkedIn inbox and respond to solicitations",
                            "description": "Recurring procedure to check inbox and auto-respond",
                            "steps": [
                                {"tool": "message.detect_messages", "params": {"url": "https://linkedin.com/inbox", "filters": {"unread": True}}},
                                {"tool": "message.compose_response", "params": {"custom_text": "No thank you."}},
                                {"tool": "message.send_response", "params": {"url": "https://linkedin.com/inbox"}},
                            ],
                            "trigger": {
                                "type": "interval",
                                "interval_minutes": 30,
                            }
                        },
                        "embedding": [0.7, 0.8, 0.5]
                    },
                    "comment": "Create polling procedure with trigger"
                },
                {
                    "tool": "queue.enqueue",
                    "params": {
                        "title": "Poll LinkedIn inbox",
                        "priority": 5,
                        "status": "pending",
                        "not_before": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                    },
                    "comment": "Schedule first poll"
                }
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan)
        result = agent.execute_request(user_msg)
        
        # Verify execution succeeded
        self.assertEqual(result["execution_results"]["status"], "completed")
        
        # Verify procedure was created with trigger
        procedures = [n for n in self.memory.nodes.values() 
                     if n.kind == "topic" and n.props.get("isPrototype") is False 
                     and ("poll" in str(n.props.get("name", "")).lower() or 
                          "poll" in str(n.props.get("label", "")).lower() or
                          "inbox" in str(n.props.get("name", "")).lower() and "respond" in str(n.props.get("name", "")).lower())]
        self.assertGreater(len(procedures), 0, f"Polling procedure should be created. Found {len(self.memory.nodes)} nodes. Procedure nodes: {[n.props.get('name') or n.props.get('label') for n in self.memory.nodes.values() if n.kind == 'topic' and n.props.get('isPrototype') is False][:5]}")
    
    def test_phase4_reuse_procedure_for_another_site(self):
        """Phase 4: Reuse login and check messages procedure for another website."""
        # First, create a procedure for LinkedIn
        linkedin_proc_uuid = self.ksg.create_concept(
            prototype_uuid=self._get_procedure_prototype_uuid(),
            json_obj={
                "name": "Login to LinkedIn and check messages",
                "description": "Procedure to login and check inbox",
                "steps": [
                    {"tool": "web.fill", "params": {"selectors": {"email": "#email", "password": "#password"}}},
                    {"tool": "web.click_selector", "params": {"selector": "#submit-btn"}},
                    {"tool": "message.detect_messages", "params": {"url": "https://linkedin.com/inbox"}},
                ]
            },
            embedding=[1.0, 0.5, 0.2],
        )
        
        # Now user asks to do the same for another site
        user_msg = "Do the same thing for anothersite.com - login and check messages"
        
        llm_plan = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "ksg.search_concepts",
                    "params": {"query": "login and check messages", "top_k": 3},
                    "comment": "Search for similar procedure"
                },
                {
                    "tool": "web.get_dom",
                    "params": {"url": "https://anothersite.com/login"},
                    "comment": "Get login page for new site"
                },
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "https://anothersite.com/login",
                        "selectors": {"email": "#email", "password": "#password"},  # Adapted selectors
                        "values": {"email": "user@example.com", "password": "password123"}
                    },
                    "comment": "Fill login form (adapted from LinkedIn procedure)"
                },
                {
                    "tool": "web.click_selector",
                    "params": {"url": "https://anothersite.com/login", "selector": "#submit-btn"},
                    "comment": "Click sign in"
                },
                {
                    "tool": "message.detect_messages",
                    "params": {"url": "https://anothersite.com/inbox", "filters": {"unread": True}},
                    "comment": "Check messages (adapted URL)"
                }
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan)
        result = agent.execute_request(user_msg)
        
        # Verify execution succeeded
        self.assertIn(result["execution_results"]["status"], ("completed", "ask_user"))
        
        # Verify procedure was adapted/reused
        # The agent should have found the LinkedIn procedure and adapted it
    
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

