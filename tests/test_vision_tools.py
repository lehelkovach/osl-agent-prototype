"""
Tests for vision-based element detection tools.
"""

import os
import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock

from src.personal_assistant.vision_tools import (
    VisionTools,
    VisionLLMTools,
    MockVisionTools,
    create_llm_client,
)
from src.personal_assistant.llm_client import OpenAIClient, ClaudeClient, GeminiClient


class TestMockVisionTools:
    """Test mock vision tools for unit testing."""
    
    def test_mock_parse_screenshot(self):
        """Test mock vision tools parse_screenshot."""
        vision = MockVisionTools()
        result = vision.parse_screenshot("fake_path.png", "login button", "https://example.com")
        
        assert result["status"] == "success"
        assert result["found"] is True
        assert "bbox" in result
        assert result["bbox"]["x"] == 100
        assert result["confidence"] == 0.85
        assert "selector_hint" in result
    
    def test_mock_locate_elements(self):
        """Test mock vision tools locate_elements."""
        vision = MockVisionTools()
        result = vision.locate_elements("fake_path.png", ["input", "button"], "https://example.com")
        
        assert result["status"] == "success"
        assert "elements" in result
        assert len(result["elements"]) == 2
        assert result["elements"][0]["type"] == "input"
        assert result["elements"][1]["type"] == "button"


class TestVisionLLMTools:
    """Test vision LLM tools with mocked LLM clients."""
    
    def test_vision_support_detection_openai(self):
        """Test vision support detection for OpenAI."""
        mock_client = Mock(spec=OpenAIClient)
        mock_client.chat_model = "gpt-4o"
        vision = VisionLLMTools(mock_client)
        assert vision.supports_vision is True
    
    def test_vision_support_detection_openai_no_vision(self):
        """Test vision support detection for OpenAI without vision model."""
        mock_client = Mock(spec=OpenAIClient)
        mock_client.chat_model = "gpt-3.5-turbo"
        vision = VisionLLMTools(mock_client)
        assert vision.supports_vision is False
    
    def test_vision_support_detection_claude(self):
        """Test vision support detection for Claude."""
        mock_client = Mock(spec=ClaudeClient)
        mock_client.chat_model = "claude-3-5-sonnet-20241022"
        vision = VisionLLMTools(mock_client)
        assert vision.supports_vision is True
    
    def test_vision_support_detection_gemini(self):
        """Test vision support detection for Gemini."""
        mock_client = Mock(spec=GeminiClient)
        vision = VisionLLMTools(mock_client)
        assert vision.supports_vision is True
    
    def test_parse_screenshot_file_not_found(self):
        """Test parse_screenshot with non-existent file."""
        mock_client = Mock(spec=OpenAIClient)
        mock_client.chat_model = "gpt-4o"
        vision = VisionLLMTools(mock_client)
        
        result = vision.parse_screenshot("nonexistent.png", "button")
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()
    
    @patch('src.personal_assistant.vision_tools.os.path.exists')
    @patch('src.personal_assistant.vision_tools.open')
    @patch('src.personal_assistant.vision_tools.base64.b64encode')
    def test_parse_screenshot_openai_success(self, mock_b64, mock_open, mock_exists):
        """Test parse_screenshot with OpenAI (mocked)."""
        mock_exists.return_value = True
        mock_b64.return_value = b"fake_base64"
        
        mock_client = Mock(spec=OpenAIClient)
        mock_client.chat_model = "gpt-4o"
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"found": true, "bbox": {"x": 100, "y": 200, "width": 150, "height": 40}, "confidence": 0.95, "description": "login button"}'
        mock_client.client = Mock()
        mock_client.client.chat.completions.create.return_value = mock_response
        
        vision = VisionLLMTools(mock_client)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(b"fake image data")
            temp_path = f.name
        
        try:
            result = vision.parse_screenshot(temp_path, "login button", "https://example.com")
            assert result["status"] == "success"
            assert result["found"] is True
            assert result["bbox"]["x"] == 100
            assert result["confidence"] == 0.95
        finally:
            os.unlink(temp_path)
    
    @patch('src.personal_assistant.vision_tools.os.path.exists')
    def test_parse_screenshot_no_vision_support(self, mock_exists):
        """Test parse_screenshot when vision not supported."""
        mock_exists.return_value = True
        
        mock_client = Mock(spec=OpenAIClient)
        mock_client.chat_model = "gpt-3.5-turbo"
        vision = VisionLLMTools(mock_client)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(b"fake image data")
            temp_path = f.name
        
        try:
            result = vision.parse_screenshot(temp_path, "button")
            assert result["status"] == "error"
            assert "not supported" in result["error"].lower()
        finally:
            os.unlink(temp_path)


class TestVisionIntegration:
    """Integration tests for vision tools (require real API keys)."""
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("USE_FAKE_OPENAI") == "1",
        reason="OpenAI API key not available or USE_FAKE_OPENAI=1"
    )
    def test_vision_parse_screenshot_real_openai(self):
        """Test vision parse_screenshot with real OpenAI (if gpt-4o available)."""
        # Create a simple test image
        from PIL import Image
        import io
        
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(img_bytes.read())
            temp_path = f.name
        
        try:
            client = create_llm_client(provider="openai")
            # Check if model supports vision
            if "gpt-4o" in client.chat_model.lower() or "gpt-4-turbo" in client.chat_model.lower():
                vision = VisionLLMTools(client)
                result = vision.parse_screenshot(temp_path, "red square", "https://test.com")
                
                # Should get a response (may or may not find the element)
                assert result["status"] in ("success", "error")
                if result["status"] == "success":
                    assert "found" in result
        finally:
            os.unlink(temp_path)


class TestVisionWithAgent:
    """Test vision tools integrated with agent."""
    
    def test_agent_with_vision_tools(self):
        """Test agent can use vision tools."""
        from src.personal_assistant.agent import PersonalAssistantAgent
        from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools
        from src.personal_assistant.openai_client import FakeOpenAIClient
        
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        vision = MockVisionTools()
        openai_client = FakeOpenAIClient()
        
        agent = PersonalAssistantAgent(
            memory=memory,
            calendar=calendar,
            tasks=tasks,
            vision=vision,
            openai_client=openai_client,
        )
        
        assert agent.vision is not None
        assert isinstance(agent.vision, MockVisionTools)
    
    def test_agent_execute_vision_tool(self):
        """Test agent can execute vision.parse_screenshot tool."""
        from src.personal_assistant.agent import PersonalAssistantAgent
        from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools
        from src.personal_assistant.openai_client import FakeOpenAIClient
        
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        vision = MockVisionTools()
        openai_client = FakeOpenAIClient()
        
        agent = PersonalAssistantAgent(
            memory=memory,
            calendar=calendar,
            tasks=tasks,
            vision=vision,
            openai_client=openai_client,
        )
        
        plan = {
            "intent": "test",
            "steps": [
                {
                    "tool": "vision.parse_screenshot",
                    "params": {
                        "screenshot_path": "test.png",
                        "query": "login button",
                        "url": "https://example.com"
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
        assert result["steps"][0].get("found") is True
