import os
import pathlib
import unittest

from src.personal_assistant.web_tools import PlaywrightWebTools


class TestWebPlaywrightActions(unittest.TestCase):
    def test_dom_locate_fill_click(self):
        web = PlaywrightWebTools(headless=True, capture_dir="/tmp/agent-captures-test")
        fixture_path = pathlib.Path(__file__).parent / "fixtures" / "linkedin_mock.html"
        url = f"file://{fixture_path}"

        dom = web.get_dom(url)
        self.assertIn("Sign in", dom["html"])
        self.assertTrue(dom.get("screenshot_base64"))

        bbox_res = web.locate_bounding_box(url, "#login-button")
        self.assertIn("bbox", bbox_res)
        self.assertIsNotNone(bbox_res["bbox"])

        fill_user = web.fill(url, "#username", "alice")
        fill_pass = web.fill(url, "#password", "hunter2")
        self.assertIn("screenshot_path", fill_user)
        if fill_user["screenshot_path"]:
            self.assertTrue(os.path.exists(fill_user["screenshot_path"]))

        click_res = web.click_selector(url, "#login-button")
        self.assertIn("screenshot_path", click_res)
        if click_res["screenshot_path"]:
            self.assertTrue(os.path.exists(click_res["screenshot_path"]))


if __name__ == "__main__":
    unittest.main()
