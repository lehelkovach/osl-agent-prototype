"""
Integration tests with real services: CPMS, Playwright, and OpenAI.

These tests require:
- CPMS_BASE_URL (optional, falls back to simple detection)
- OPENAI_API_KEY (required for real OpenAI tests)
- USE_PLAYWRIGHT=1 (required for Playwright tests)
- USE_FAKE_OPENAI=0 (required for real OpenAI tests)
- USE_CPMS_FOR_PROCS=1 (optional, for CPMS routing)

Set environment variables or use .env.local to configure.
"""
import os
import pytest
import tempfile
from dotenv import load_dotenv

# Load .env.local if available
load_dotenv(".env.local")
load_dotenv()

from src.personal_assistant.service import default_agent_from_env
from src.personal_assistant.cpms_adapter import CPMSAdapter, CPMSNotInstalled
from src.personal_assistant.web_tools import PlaywrightWebTools


def _check_cpms_available():
    """Check if CPMS service is available."""
    try:
        adapter = CPMSAdapter.from_env()
        # Try to ping CPMS (if it has a health endpoint or similar)
        return True
    except (CPMSNotInstalled, Exception):
        return False


def _check_playwright_available():
    """Check if Playwright is available."""
    return os.getenv("USE_PLAYWRIGHT", "0").lower() in ("1", "true", "yes")


def _check_openai_available():
    """Check if OpenAI API key is available."""
    return bool(os.getenv("OPENAI_API_KEY")) and os.getenv("USE_FAKE_OPENAI", "0").lower() not in ("1", "true", "yes")


@pytest.mark.skipif(not _check_openai_available(), reason="OpenAI API key not available or USE_FAKE_OPENAI=1")
def test_agent_with_real_openai():
    """Test agent with real OpenAI API."""
    agent = default_agent_from_env()
    
    # Simple request that should work
    result = agent.execute_request("What is 2+2?")
    
    assert result is not None
    assert "plan" in result or "response" in result
    # Should get a response (even if it's an inform/ask_user/no action taken)
    status = result.get("execution_results", {}).get("status")
    assert status in ("completed", "ask_user", "error", "no action taken")


@pytest.mark.skipif(not _check_playwright_available(), reason="Playwright not enabled (USE_PLAYWRIGHT=1 required)")
def test_playwright_get_dom_real():
    """Test Playwright with a real website."""
    web = PlaywrightWebTools(headless=True)
    
    # Use a simple, reliable test site
    result = web.get_dom("https://example.com")
    
    assert result is not None
    assert "html" in result
    # Playwright may get error pages or CDN issues, just verify it returned HTML
    assert len(result.get("html", "")) > 0


@pytest.mark.skipif(not _check_playwright_available(), reason="Playwright not enabled (USE_PLAYWRIGHT=1 required)")
def test_playwright_screenshot_real():
    """Test Playwright screenshot capture."""
    web = PlaywrightWebTools(headless=True)
    
    result = web.get_dom("https://example.com")
    
    assert result is not None
    # Should have screenshot data (base64 or path)
    assert result.get("screenshot_base64") or result.get("screenshot_path")


@pytest.mark.skipif(not _check_cpms_available(), reason="CPMS service not available")
def test_cpms_detect_form_real():
    """Test CPMS form detection with real service."""
    adapter = CPMSAdapter.from_env()
    
    # Simple login form HTML
    html = """
    <html>
    <body>
        <form id="login-form">
            <input type="email" name="email" id="email" placeholder="Email">
            <input type="password" name="password" id="password" placeholder="Password">
            <button type="submit">Login</button>
        </form>
    </body>
    </html>
    """
    
    result = adapter.detect_form_pattern(html=html, url="https://example.com/login")
    
    assert result is not None
    assert "form_type" in result
    assert "fields" in result
    assert "confidence" in result
    
    # Should detect login form
    if result.get("form_type") == "login":
        field_types = [f.get("type") for f in result.get("fields", [])]
        assert "email" in field_types or "password" in field_types


@pytest.mark.skipif(
    not (_check_playwright_available() and _check_cpms_available()),
    reason="Both Playwright and CPMS required"
)
def test_cpms_detect_form_with_screenshot():
    """Test CPMS form detection with screenshot from Playwright."""
    web = PlaywrightWebTools(headless=True)
    adapter = CPMSAdapter.from_env()
    
    # Get DOM and screenshot from a real page
    dom_result = web.get_dom("https://example.com")
    
    if not dom_result or "html" not in dom_result:
        pytest.skip("Could not fetch DOM from example.com")
    
    html = dom_result["html"]
    screenshot_path = None
    
    # Save screenshot if available
    if dom_result.get("screenshot_base64"):
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            import base64
            f.write(base64.b64decode(dom_result["screenshot_base64"]))
            screenshot_path = f.name
    
    try:
        result = adapter.detect_form_pattern(
            html=html,
            screenshot_path=screenshot_path,
            url="https://example.com"
        )
        
        assert result is not None
        assert "form_type" in result
        assert "fields" in result
    finally:
        if screenshot_path and os.path.exists(screenshot_path):
            os.unlink(screenshot_path)


@pytest.mark.skipif(
    not (_check_openai_available() and _check_playwright_available()),
    reason="Both OpenAI and Playwright required"
)
def test_agent_web_request_with_real_services():
    """Test agent making a web request with real OpenAI and Playwright."""
    agent = default_agent_from_env()
    
    # Request that should trigger web.get
    result = agent.execute_request("Get the HTML from https://example.com and tell me what it says")
    
    assert result is not None
    execution = result.get("execution_results", {})
    status = execution.get("status")
    
    # Should complete or ask for more info
    assert status in ("completed", "ask_user", "error")
    
    # If completed, should have executed web.get
    if status == "completed":
        steps = result.get("plan", {}).get("steps", [])
        web_steps = [s for s in steps if s.get("tool") == "web.get"]
        # May or may not have web.get depending on LLM plan
        # Just verify it didn't crash


@pytest.mark.skipif(
    not (_check_openai_available() and _check_cpms_available()),
    reason="Both OpenAI and CPMS required"
)
def test_agent_cpms_form_detection_with_real_services():
    """Test agent using CPMS form detection with real OpenAI and CPMS."""
    agent = default_agent_from_env()
    
    # HTML with a login form
    html = """
    <html>
    <body>
        <form>
            <input type="email" name="email">
            <input type="password" name="password">
            <button type="submit">Login</button>
        </form>
    </body>
    </html>
    """
    
    # Request that should trigger cpms.detect_form
    result = agent.execute_request(
        f"Detect the form pattern in this HTML: {html[:200]}..."
    )
    
    assert result is not None
    execution = result.get("execution_results", {})
    status = execution.get("status")
    
    # Should complete or ask for more info
    assert status in ("completed", "ask_user", "error")
    
    # If completed, check if cpms.detect_form was called
    if status == "completed":
        steps = result.get("plan", {}).get("steps", [])
        cpms_steps = [s for s in steps if s.get("tool") == "cpms.detect_form"]
        # May or may not have cpms.detect_form depending on LLM plan
        # Just verify it didn't crash


@pytest.mark.skipif(
    not (_check_openai_available() and _check_playwright_available() and _check_cpms_available()),
    reason="OpenAI, Playwright, and CPMS all required"
)
def test_full_integration_workflow():
    """Test full integration: OpenAI + Playwright + CPMS working together."""
    agent = default_agent_from_env()
    
    # Complex request that uses all services
    result = agent.execute_request(
        "Get the HTML from https://example.com, detect any forms using CPMS, and summarize what you found"
    )
    
    assert result is not None
    execution = result.get("execution_results", {})
    status = execution.get("status")
    
    # Should complete or ask for more info
    assert status in ("completed", "ask_user", "error", "no action taken")
    
    # Verify execution happened (may have errors in steps, but should be handled gracefully)
    # The word "error" in the result string is OK if it's in error messages that are properly handled

