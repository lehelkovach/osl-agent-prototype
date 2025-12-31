import os
import pathlib
import unittest

import pytest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_OK = True
except Exception:
    PLAYWRIGHT_OK = False


@pytest.mark.skipif(not PLAYWRIGHT_OK, reason="Playwright not available")
class TestWebLinkedInLoginFlow(unittest.TestCase):
    def test_login_with_recalled_credentials(self):
        memory = MockMemoryTools()
        remember_plan = """
        {
          "intent": "remember",
          "steps": [
            {
              "tool": "memory.remember",
              "params": {
                "text": "linkedin.com credentials",
                "kind": "Credential",
                "props": {
                  "appName": "LinkedIn",
                  "url": "https://linkedin.com",
                  "username": "ada",
                  "password": "hunter2"
                }
              }
            }
          ]
        }
        """
        remember_agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            openai_client=FakeOpenAIClient(chat_response=remember_plan, embedding=[0.9, 0.1, 0.0]),
        )
        remember_agent.execute_request("remember my linkedin login")

        # Recall credentials via embedding search
        results = memory.search("linkedin credentials", top_k=5, query_embedding=[0.9, 0.1, 0.0])
        cred = next((r for r in results if r.get("kind") == "Credential"), None)
        self.assertIsNotNone(cred)

        # Use Playwright against fixture page
        fixture_path = pathlib.Path(__file__).parent / "fixtures" / "linkedin_mock.html"
        url = f"file://{fixture_path}"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)
            page.fill("#username", cred["props"]["username"])
            page.fill("#password", cred["props"]["password"])
            page.click("#login-button")
            status = page.text_content("#status")
            browser.close()
        self.assertIn("Welcome", status)
        self.assertIn(cred["props"]["username"], status)


if __name__ == "__main__":
    unittest.main()
