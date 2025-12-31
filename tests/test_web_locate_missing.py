import unittest

from src.personal_assistant.web_tools import PlaywrightWebTools


class TestWebLocateMissing(unittest.TestCase):
    def test_locate_missing_returns_404(self):
        web = PlaywrightWebTools(headless=True)
        data_url = "data:text/html,<html><body><div id='present'>hi</div></body></html>"
        res = web.locate_bounding_box(data_url, "#absent")
        self.assertEqual(res["status"], 404)
        self.assertIsNone(res["bbox"])


if __name__ == "__main__":
    unittest.main()
