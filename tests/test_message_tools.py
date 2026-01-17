"""
Tests for message detection and autorespond tools.
"""

import os
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.personal_assistant.message_tools import (
    MessageTools,
    WebMessageTools,
    MockMessageTools,
)


class TestMockMessageTools:
    """Test mock message tools for unit testing."""
    
    def test_mock_detect_messages(self):
        """Test mock message tools detect_messages."""
        messages = MockMessageTools()
        result = messages.detect_messages("https://mail.example.com/inbox")
        
        assert result["status"] == "success"
        assert "messages" in result
        assert result["count"] == 2
        assert len(result["messages"]) == 2
        assert result["messages"][0]["unread"] is True
    
    def test_mock_detect_messages_with_filters(self):
        """Test mock message tools detect_messages with filters."""
        messages = MockMessageTools()
        result = messages.detect_messages(
            "https://mail.example.com/inbox",
            filters={"unread": True}
        )
        
        assert result["status"] == "success"
        assert result["count"] == 1
        assert all(m["unread"] for m in result["messages"])
    
    def test_mock_get_message_details(self):
        """Test mock message tools get_message_details."""
        messages = MockMessageTools()
        result = messages.get_message_details("https://mail.example.com/inbox", "msg_1")
        
        assert result["status"] == "success"
        assert result["message_id"] == "msg_1"
        assert "from" in result
        assert "subject" in result
        assert "body" in result
    
    def test_mock_compose_response(self):
        """Test mock message tools compose_response."""
        messages = MockMessageTools()
        message = {"from": "sender@example.com", "subject": "Hello"}
        
        result = messages.compose_response(message, template="auto_reply")
        
        assert result["status"] == "success"
        assert result["to"] == "sender@example.com"
        assert "Re: Hello" in result["subject"]
        assert len(result["body"]) > 0
    
    def test_mock_compose_response_custom_text(self):
        """Test mock message tools compose_response with custom text."""
        messages = MockMessageTools()
        message = {"from": "sender@example.com", "subject": "Hello"}
        
        result = messages.compose_response(message, custom_text="Custom response")
        
        assert result["status"] == "success"
        assert result["body"] == "Custom response"
    
    def test_mock_send_response(self):
        """Test mock message tools send_response."""
        messages = MockMessageTools()
        response = {
            "to": "recipient@example.com",
            "subject": "Re: Test",
            "body": "Response text"
        }
        
        result = messages.send_response("https://mail.example.com/inbox", response)
        
        assert result["status"] == "success"
        assert result["response_sent"] is True
        assert "sent_at" in result


class TestWebMessageTools:
    """Test web-based message tools with mocked web tools."""
    
    def test_detect_messages_with_mock_web(self):
        """Test detect_messages with mocked web tools."""
        mock_web = Mock()
        mock_web.get_dom.return_value = {
            "html": '<div class="message unread"><div class="subject">Test Message</div></div>',
            "status": 200
        }
        
        messages = WebMessageTools(mock_web)
        result = messages.detect_messages("https://mail.example.com/inbox")
        
        assert result["status"] == "success"
        assert "messages" in result
        mock_web.get_dom.assert_called_once_with("https://mail.example.com/inbox")
    
    def test_detect_messages_error_handling(self):
        """Test detect_messages error handling."""
        mock_web = Mock()
        mock_web.get_dom.side_effect = Exception("Network error")
        
        messages = WebMessageTools(mock_web)
        result = messages.detect_messages("https://mail.example.com/inbox")
        
        assert result["status"] == "error"
        assert "error" in result
    
    def test_get_message_details_with_mock_web(self):
        """Test get_message_details with mocked web tools."""
        mock_web = Mock()
        mock_web.get_dom.return_value = {
            "html": '<div class="from">sender@example.com</div><div class="subject">Test</div><div class="body">Body text</div>',
            "status": 200
        }
        
        messages = WebMessageTools(mock_web)
        result = messages.get_message_details("https://mail.example.com/inbox", "msg_1")
        
        assert result["status"] == "success"
        assert result["message_id"] == "msg_1"
        mock_web.get_dom.assert_called_once_with("https://mail.example.com/inbox")
    
    def test_compose_response_default(self):
        """Test compose_response with default template."""
        mock_web = Mock()
        messages = WebMessageTools(mock_web)
        
        message = {"from": "sender@example.com", "subject": "Hello"}
        result = messages.compose_response(message)
        
        assert result["status"] == "success"
        assert result["to"] == "sender@example.com"
        assert "Re: Hello" in result["subject"]
        assert len(result["body"]) > 0
    
    def test_compose_response_with_template(self):
        """Test compose_response with specific template."""
        mock_web = Mock()
        messages = WebMessageTools(mock_web)
        
        message = {"from": "sender@example.com", "subject": "Hello"}
        result = messages.compose_response(message, template="acknowledgment")
        
        assert result["status"] == "success"
        assert "Thank you" in result["body"]
    
    def test_send_response_with_mock_web(self):
        """Test send_response with mocked web tools."""
        mock_web = Mock()
        mock_web.click_selector.return_value = {"status": 200}
        mock_web.get_dom.return_value = {"html": "<form></form>", "status": 200}
        mock_web.fill.return_value = {"status": 200}
        
        messages = WebMessageTools(mock_web)
        response = {
            "to": "recipient@example.com",
            "subject": "Re: Test",
            "body": "Response text"
        }
        
        result = messages.send_response("https://mail.example.com/inbox", response)
        
        assert result["status"] == "success"
        assert result["response_sent"] is True


class TestMessageIntegration:
    """Integration tests for message tools (require real web tools)."""
    
    @pytest.mark.skipif(
        os.getenv("USE_PLAYWRIGHT", "0") != "1",
        reason="Playwright not enabled (USE_PLAYWRIGHT=1 required)"
    )
    def test_detect_messages_real_web(self):
        """Test detect_messages with real web tools (if Playwright available)."""
        from src.personal_assistant.web_tools import PlaywrightWebTools
        
        web = PlaywrightWebTools(headless=True)
        messages = WebMessageTools(web)
        
        # Use a simple test page (example.com doesn't have messages, but tests the flow)
        result = messages.detect_messages("https://example.com")
        
        # Should handle gracefully even if no messages found
        assert result["status"] in ("success", "error")
        if result["status"] == "success":
            assert "messages" in result


class TestMessageWithAgent:
    """Test message tools integrated with agent."""
    
    def test_agent_with_message_tools(self):
        """Test agent can use message tools."""
        from src.personal_assistant.agent import PersonalAssistantAgent
        from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools, MockWebTools
        from src.personal_assistant.openai_client import FakeOpenAIClient
        
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        messages = MockMessageTools()
        openai_client = FakeOpenAIClient()
        
        agent = PersonalAssistantAgent(
            memory=memory,
            calendar=calendar,
            tasks=tasks,
            web=web,
            messages=messages,
            openai_client=openai_client,
        )
        
        assert agent.messages is not None
        assert isinstance(agent.messages, MockMessageTools)
    
    def test_agent_execute_detect_messages(self):
        """Test agent can execute message.detect_messages tool."""
        from src.personal_assistant.agent import PersonalAssistantAgent
        from src.personal_assistant.mock_tools import (
            MockMemoryTools, MockCalendarTools, MockTaskTools, MockWebTools
        )
        from src.personal_assistant.openai_client import FakeOpenAIClient
        
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        messages = MockMessageTools()
        openai_client = FakeOpenAIClient()
        
        agent = PersonalAssistantAgent(
            memory=memory,
            calendar=calendar,
            tasks=tasks,
            web=web,
            messages=messages,
            openai_client=openai_client,
        )
        
        plan = {
            "intent": "test",
            "steps": [
                {
                    "tool": "message.detect_messages",
                    "params": {
                        "url": "https://mail.example.com/inbox",
                        "filters": {"unread": True}
                    }
                }
            ]
        }
        
        from src.personal_assistant.models import Provenance
        from datetime import datetime, timezone
        
        provenance = Provenance(
            source="test",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="test-trace",
        )
        
        result = agent._execute_plan(plan, provenance)
        
        assert result["status"] == "completed"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["status"] == "success"
        assert "messages" in result["steps"][0]
    
    def test_agent_execute_compose_and_send_response(self):
        """Test agent can execute compose and send response tools."""
        from src.personal_assistant.agent import PersonalAssistantAgent
        from src.personal_assistant.mock_tools import (
            MockMemoryTools, MockCalendarTools, MockTaskTools, MockWebTools
        )
        from src.personal_assistant.openai_client import FakeOpenAIClient
        
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        messages = MockMessageTools()
        openai_client = FakeOpenAIClient()
        
        agent = PersonalAssistantAgent(
            memory=memory,
            calendar=calendar,
            tasks=tasks,
            web=web,
            messages=messages,
            openai_client=openai_client,
        )
        
        plan = {
            "intent": "test",
            "steps": [
                {
                    "tool": "message.compose_response",
                    "params": {
                        "message": {"from": "sender@example.com", "subject": "Hello"},
                        "template": "auto_reply"
                    }
                },
                {
                    "tool": "message.send_response",
                    "params": {
                        "url": "https://mail.example.com/inbox",
                        "response": {"to": "sender@example.com", "subject": "Re: Hello", "body": "Thank you"},
                        "message": {"from": "sender@example.com", "subject": "Hello"}
                    }
                }
            ]
        }
        
        from src.personal_assistant.models import Provenance
        from datetime import datetime, timezone
        
        provenance = Provenance(
            source="test",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="test-trace",
        )
        
        result = agent._execute_plan(plan, provenance)
        
        assert result["status"] == "completed"
        assert len(result["steps"]) == 2
        assert result["steps"][0]["status"] == "success"  # compose
        assert result["steps"][1]["status"] == "success"  # send
        assert result["steps"][1].get("response_sent") is True
