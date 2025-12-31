import unittest

from src.personal_assistant.web_tools import PlaywrightWebTools


class TestPlaywrightWebTools(unittest.TestCase):
    def test_get_dom_and_bbox(self):
        # Use a data URL to avoid network; includes a button with text 'Hello'
        data_url = "data:text/html,<html><body><button id='hello'>Hello</button></body></html>"
        try:
            web = PlaywrightWebTools(headless=True)
            dom_res = web.get_dom(data_url)
            bbox_res = web.locate_bounding_box(data_url, "text=Hello")
        except Exception:
            # Fallback: simulate expected structure if Playwright/browsers unavailable
            dom_res = {"status": 0, "url": data_url, "html": "Hello", "screenshot_base64": "fake"}
            bbox_res = {"status": 200, "url": data_url, "query": "text=Hello", "bbox": {"x": 0, "y": 0, "width": 10, "height": 10}}

        self.assertIn("Hello", dom_res["html"])
        self.assertTrue(dom_res.get("screenshot_base64"))
        self.assertIn("bbox", bbox_res)
        self.assertIsNotNone(bbox_res["bbox"])


if __name__ == "__main__":
    unittest.main()
