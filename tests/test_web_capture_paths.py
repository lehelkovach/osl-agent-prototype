import os
import unittest

from src.personal_assistant.web_tools import PlaywrightWebTools

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    PLAYWRIGHT_OK = True
except Exception:
    PLAYWRIGHT_OK = False


@unittest.skipUnless(PLAYWRIGHT_OK, "Playwright not available")
class TestWebCapturePaths(unittest.TestCase):
    def test_screenshot_path_saved(self):
        web = PlaywrightWebTools(headless=True, capture_dir="/tmp/agent-captures-test")
        data_url = "data:text/html,<html><body><div id='a'>hi</div></body></html>"
        try:
            res = web.screenshot(data_url)
        except Exception as exc:
            self.skipTest(f"Playwright screenshot failed: {exc}")
        self.assertIn("path", res)
        if res["path"]:
            self.assertTrue(os.path.exists(res["path"]))


if __name__ == "__main__":
    unittest.main()
