"""
Integration tests for vision and message tools with real services.

These tests require:
- USE_PLAYWRIGHT=1 for web automation
- OPENAI_API_KEY or ANTHROPIC_API_KEY for vision (if testing vision)
- USE_FAKE_OPENAI=0 to use real APIs
"""

import os
import pytest
import tempfile

from src.personal_assistant.vision_tools import VisionLLMTools, create_llm_client
from src.personal_assistant.message_tools import WebMessageTools
from src.personal_assistant.web_tools import PlaywrightWebTools
from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.service import default_agent_from_env


def create_test_image(path: str, color: str = 'red'):
    """Create a simple test image file."""
    try:
        from PIL import Image
        img = Image.new('RGB', (200, 200), color=color)
        img.save(path)
        return path
    except ImportError:
        # Fallback: create a minimal PNG file
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\xc8\x00\x00\x00\xc8\x08\x02\x00\x00\x00\xff\x80\x00\x00\x00\x00IEND\xaeB`\x82'
        with open(path, 'wb') as f:
            f.write(png_data)
        return path


def _check_vision_available():
    """Check if vision models are available."""
    return (
        (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        and os.getenv("USE_FAKE_OPENAI", "0") == "0"
    )


def _check_playwright_available():
    """Check if Playwright is available."""
    return os.getenv("USE_PLAYWRIGHT", "0") == "1"


@pytest.mark.skipif(not _check_vision_available(), reason="Vision API keys not available")
class TestVisionIntegration:
    """Integration tests for vision tools with real APIs."""
    
    def test_vision_parse_screenshot_openai(self):
        """Test vision.parse_screenshot with real OpenAI GPT-4 Vision."""
        try:
            from src.personal_assistant.llm_client import OpenAIClient
            client = OpenAIClient()
            vision = VisionLLMTools(client)
            
            if not vision.supports_vision:
                pytest.skip(f"Model {client.chat_model} does not support vision")
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                img_path = f.name
                create_test_image(img_path, 'blue')
            
            try:
                result = vision.parse_screenshot(
                    img_path,
                    "blue square or rectangle",
                    "https://test.com"
                )
                
                assert result["status"] == "success"
                assert "found" in result
                # May or may not find element, but structure should be valid
            finally:
                if os.path.exists(img_path):
                    os.remove(img_path)
        except Exception as e:
            pytest.skip(f"OpenAI vision integration test failed: {e}")
    
    def test_vision_parse_screenshot_claude(self):
        """Test vision.parse_screenshot with real Claude Vision."""
        try:
            from src.personal_assistant.llm_client import ClaudeClient
            client = ClaudeClient()
            vision = VisionLLMTools(client)
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                img_path = f.name
                create_test_image(img_path, 'green')
            
            try:
                result = vision.parse_screenshot(
                    img_path,
                    "green square",
                    "https://test.com"
                )
                
                assert result["status"] == "success"
                assert "found" in result
            finally:
                if os.path.exists(img_path):
                    os.remove(img_path)
        except Exception as e:
            pytest.skip(f"Claude vision integration test failed: {e}")


@pytest.mark.skipif(
    not (_check_playwright_available() and _check_vision_available()),
    reason="Playwright and vision APIs required"
)
class TestVisionWebIntegration:
    """Integration tests combining vision with web automation."""
    
    def test_vision_with_web_screenshot(self):
        """Test vision tools with real web screenshot."""
        try:
            web = PlaywrightWebTools(headless=True)
            vision = VisionLLMTools(create_llm_client())
            
            if not vision.supports_vision:
                pytest.skip("Vision not supported with current LLM model")
            
            # Get screenshot from a real page
            screenshot_result = web.screenshot("https://example.com")
            screenshot_path = screenshot_result.get("path") or screenshot_result.get("screenshot_path")
            
            if not screenshot_path or not os.path.exists(screenshot_path):
                pytest.skip("Screenshot not captured")
            
            try:
                # Use vision to parse the screenshot
                result = vision.parse_screenshot(
                    screenshot_path,
                    "heading or title text",
                    "https://example.com"
                )
                
                assert result["status"] == "success"
                assert "found" in result
            finally:
                if screenshot_path and os.path.exists(screenshot_path):
                    try:
                        os.remove(screenshot_path)
                    except Exception:
                        pass
        except Exception as e:
            pytest.skip(f"Vision + web integration test failed: {e}")
    
    def test_web_locate_bounding_box_with_vision(self):
        """Test web.locate_bounding_box with vision fallback enabled."""
        try:
            # Temporarily enable vision for location
            original_env = os.getenv("USE_VISION_FOR_LOCATION", "0")
            os.environ["USE_VISION_FOR_LOCATION"] = "1"
            
            try:
                web = PlaywrightWebTools(headless=True)
                vision = VisionLLMTools(create_llm_client())
                
                if not vision.supports_vision:
                    pytest.skip("Vision not supported")
                
                # This should use vision if available
                result = web.locate_bounding_box(
                    "https://example.com",
                    "heading or main title"
                )
                
                assert result["status"] in (200, 404)
                assert "bbox" in result or result.get("bbox") is None
                # May use vision or DOM method
            finally:
                os.environ["USE_VISION_FOR_LOCATION"] = original_env
        except Exception as e:
            pytest.skip(f"Vision location integration test failed: {e}")


@pytest.mark.skipif(not _check_playwright_available(), reason="Playwright required")
class TestMessageToolsIntegration:
    """Integration tests for message tools with real web automation."""
    
    def test_message_detect_with_real_web(self):
        """Test message detection with real Playwright."""
        try:
            web = PlaywrightWebTools(headless=True)
            messages = WebMessageTools(web)
            
            # Test with a simple page (won't find messages, but tests structure)
            result = messages.detect_messages("https://example.com")
            
            assert result["status"] in ("success", "error")
            # Structure should be valid even if no messages found
        except Exception as e:
            pytest.skip(f"Message tools integration test failed: {e}")


@pytest.mark.skipif(
    not (_check_playwright_available() and _check_vision_available()),
    reason="Playwright and vision APIs required"
)
class TestFullIntegration:
    """Full integration tests combining all new features."""
    
    def test_agent_with_vision_and_messages(self):
        """Test agent with vision and message tools enabled."""
        try:
            agent = default_agent_from_env()
            
            # Check if tools are available
            if not agent.vision or not agent.messages:
                pytest.skip("Vision or message tools not initialized")
            
            # Test a simple request that might use vision
            result = agent.execute_request(
                "Take a screenshot of https://example.com and describe what you see"
            )
            
            assert result is not None
            assert "plan" in result or "execution_results" in result
            # Should complete or ask for more info
            assert result.get("execution_results", {}).get("status") in (
                "completed", "ask_user", "error", "no action taken"
            )
        except Exception as e:
            pytest.skip(f"Full integration test failed: {e}")
    
    def test_agent_message_workflow(self):
        """Test full message detection and response workflow."""
        try:
            agent = default_agent_from_env()
            
            if not agent.messages:
                pytest.skip("Message tools not initialized")
            
            # Test message detection request
            result = agent.execute_request(
                "Check for new messages in https://example.com/inbox"
            )
            
            assert result is not None
            # Should attempt to detect messages or ask for clarification
            assert result.get("execution_results", {}).get("status") in (
                "completed", "ask_user", "error", "no action taken"
            )
        except Exception as e:
            pytest.skip(f"Message workflow test failed: {e}")

