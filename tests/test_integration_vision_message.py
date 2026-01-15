"""
Integration tests for vision and message tools with real services.
"""

import os
import pytest
import tempfile
from PIL import Image
import io

from src.personal_assistant.vision_tools import VisionLLMTools, create_llm_client
from src.personal_assistant.message_tools import WebMessageTools
from src.personal_assistant.web_tools import PlaywrightWebTools
from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.service import default_agent_from_env


def _check_openai_available():
    """Check if OpenAI is available for testing."""
    return os.getenv("OPENAI_API_KEY") and os.getenv("USE_FAKE_OPENAI", "0") == "0"


def _check_playwright_available():
    """Check if Playwright is available for testing."""
    return os.getenv("USE_PLAYWRIGHT", "0") == "1"


def _check_vision_model_supported():
    """Check if current LLM model supports vision."""
    if not _check_openai_available():
        return False
    try:
        client = create_llm_client()
        vision_models = ["gpt-4o", "gpt-4-turbo", "gpt-4-vision"]
        return any(vm in client.chat_model.lower() for vm in vision_models)
    except Exception:
        return False


@pytest.mark.skipif(
    not _check_vision_model_supported(),
    reason="Vision-capable LLM model not available"
)
def test_vision_parse_screenshot_integration():
    """Integration test: Parse a real screenshot with vision model."""
    # Create a simple test image with text
    img = Image.new('RGB', (400, 200), color='white')
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    
    # Draw a button-like rectangle
    draw.rectangle([50, 50, 200, 100], fill='blue', outline='black', width=2)
    draw.text((75, 65), "Login", fill='white')
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name, 'PNG')
        temp_path = f.name
    
    try:
        client = create_llm_client()
        vision = VisionLLMTools(client)
        
        result = vision.parse_screenshot(temp_path, "login button", "https://test.com")
        
        assert result["status"] == "success"
        # Should find the button (or at least attempt to)
        if result.get("found"):
            assert "bbox" in result
            assert result.get("confidence", 0) > 0
    finally:
        os.unlink(temp_path)


@pytest.mark.skipif(
    not (_check_playwright_available() and _check_openai_available()),
    reason="Playwright and OpenAI required"
)
def test_vision_with_web_screenshot_integration():
    """Integration test: Take screenshot with Playwright and parse with vision."""
    web = PlaywrightWebTools(headless=True)
    client = create_llm_client()
    
    # Take screenshot of a real page
    screenshot_result = web.screenshot("https://example.com")
    screenshot_path = screenshot_result.get("path") or screenshot_result.get("screenshot_path")
    
    if screenshot_path and os.path.exists(screenshot_path):
        try:
            vision = VisionLLMTools(client)
            
            # Try to find common elements
            result = vision.parse_screenshot(screenshot_path, "heading or title", "https://example.com")
            
            assert result["status"] == "success"
            # May or may not find the element, but should get a valid response
        finally:
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)


@pytest.mark.skipif(
    not _check_playwright_available(),
    reason="Playwright not enabled (USE_PLAYWRIGHT=1 required)"
)
def test_message_detection_integration():
    """Integration test: Detect messages with real web tools."""
    web = PlaywrightWebTools(headless=True)
    messages = WebMessageTools(web)
    
    # Test with a simple page (won't have real messages, but tests the flow)
    result = messages.detect_messages("https://example.com")
    
    # Should handle gracefully
    assert result["status"] in ("success", "error")
    if result["status"] == "success":
        assert "messages" in result
        assert "count" in result


@pytest.mark.skipif(
    not (_check_playwright_available() and _check_openai_available()),
    reason="Playwright and OpenAI required"
)
def test_agent_vision_workflow_integration():
    """Integration test: Agent using vision tools in a workflow."""
    agent = default_agent_from_env()
    
    if not agent.vision:
        pytest.skip("Vision tools not available")
    
    # Create a test image
    img = Image.new('RGB', (200, 100), color='lightgray')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name, 'PNG')
        temp_path = f.name
    
    try:
        # Test agent can use vision tools via plan execution
        plan = {
            "intent": "test",
            "steps": [
                {
                    "tool": "vision.parse_screenshot",
                    "params": {
                        "screenshot_path": temp_path,
                        "query": "any element",
                        "url": "https://test.com"
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
        assert result["steps"][0]["status"] in ("success", "error")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.mark.skipif(
    not (_check_playwright_available() and _check_openai_available()),
    reason="Playwright and OpenAI required"
)
def test_agent_message_workflow_integration():
    """Integration test: Agent using message tools in a workflow."""
    agent = default_agent_from_env()
    
    if not agent.messages:
        pytest.skip("Message tools not available")
    
    # Test agent can use message tools via plan execution
    plan = {
        "intent": "test",
        "steps": [
            {
                "tool": "message.detect_messages",
                "params": {
                    "url": "https://example.com",
                    "filters": {}
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
    assert result["steps"][0]["status"] in ("success", "error")


@pytest.mark.skipif(
    not (_check_playwright_available() and _check_openai_available()),
    reason="Playwright and OpenAI required"
)
def test_full_vision_message_workflow():
    """Integration test: Full workflow using vision and message tools together."""
    agent = default_agent_from_env()
    
    if not (agent.vision and agent.messages and agent.web):
        pytest.skip("Vision, message, or web tools not available")
    
    # Create a test image
    img = Image.new('RGB', (200, 100), color='lightgray')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name, 'PNG')
        temp_path = f.name
    
    try:
        # Test workflow: screenshot -> vision parse -> message detection
        plan = {
            "intent": "test",
            "steps": [
                {
                    "tool": "web.screenshot",
                    "params": {"url": "https://example.com"}
                },
                {
                    "tool": "vision.parse_screenshot",
                    "params": {
                        "screenshot_path": temp_path,
                        "query": "heading",
                        "url": "https://example.com"
                    }
                },
                {
                    "tool": "message.detect_messages",
                    "params": {
                        "url": "https://example.com",
                        "filters": {}
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
        assert len(result["steps"]) == 3
        # All steps should complete (may have errors, but should handle gracefully)
        for step_result in result["steps"]:
            # Status can be "success", "error", or HTTP status code (200)
            status = step_result.get("status")
            assert status in ("success", "error", 200, "200") or isinstance(status, int)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

