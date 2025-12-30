from typing import Dict, Any
import base64

from src.personal_assistant.tools import WebTools


class PlaywrightWebTools(WebTools):
    """
    Playwright-backed implementation for web commandlets.
    Each call launches a fresh browser context to keep it simple.
    """

    def __init__(self, browser_type: str = "chromium", headless: bool = True):
        self.browser_type = browser_type
        self.headless = headless

    def _with_page(self, url: str, action):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise RuntimeError("Playwright is not installed or failed to load") from e

        with sync_playwright() as p:
            browser_factory = getattr(p, self.browser_type)
            browser = browser_factory.launch(headless=self.headless)
            page = browser.new_page()
            try:
                return action(page, url)
            finally:
                browser.close()

    def get(self, url: str) -> Dict[str, Any]:
        def action(page, u):
            response = page.goto(u)
            body = page.content()
            return {"status": response.status if response else 0, "url": u, "body": body}

        return self._with_page(url, action)

    def post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        def action(page, u):
            page.goto("about:blank")
            body = page.evaluate(
                """async ({url, payload}) => {
                    const res = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
                    const text = await res.text();
                    return {status: res.status, body: text};
                }""",
                {"url": u, "payload": payload},
            )
            return {"status": body.get("status", 0), "url": u, "body": body.get("body")}

        return self._with_page(url, action)

    def screenshot(self, url: str) -> Dict[str, Any]:
        def action(page, u):
            response = page.goto(u)
            img_bytes = page.screenshot(full_page=True)
            return {"status": response.status if response else 0, "url": u, "image_bytes": img_bytes}

        return self._with_page(url, action)

    def get_dom(self, url: str) -> Dict[str, Any]:
        def action(page, u):
            response = page.goto(u)
            body = page.content()
            img_bytes = page.screenshot(full_page=True)
            img_b64 = base64.b64encode(img_bytes).decode("ascii")
            return {
                "status": response.status if response else 0,
                "url": u,
                "html": body,
                "screenshot_base64": img_b64,
            }

        return self._with_page(url, action)

    def click_xy(self, url: str, x: int, y: int) -> Dict[str, Any]:
        def action(page, u):
            response = page.goto(u)
            page.mouse.click(x, y)
            return {"status": response.status if response else 0, "url": u, "clicked": [x, y]}

        return self._with_page(url, action)

    def click_selector(self, url: str, selector: str) -> Dict[str, Any]:
        def action(page, u):
            response = page.goto(u)
            page.click(selector)
            return {"status": response.status if response else 0, "url": u, "selector": selector}

        return self._with_page(url, action)

    def click_xpath(self, url: str, xpath: str) -> Dict[str, Any]:
        def action(page, u):
            response = page.goto(u)
            page.click(f"xpath={xpath}")
            return {"status": response.status if response else 0, "url": u, "xpath": xpath}

        return self._with_page(url, action)

    def fill(self, url: str, selector: str, text: str) -> Dict[str, Any]:
        def action(page, u):
            response = page.goto(u)
            page.fill(selector, text)
            return {"status": response.status if response else 0, "url": u, "selector": selector, "text": text}

        return self._with_page(url, action)

    def wait_for(self, url: str, selector: str, timeout_ms: int = 5000) -> Dict[str, Any]:
        def action(page, u):
            response = page.goto(u)
            page.wait_for_selector(selector, timeout=timeout_ms)
            return {"status": response.status if response else 0, "url": u, "selector": selector}

        return self._with_page(url, action)


class AppiumUITools:
    """
    Placeholder for Appium-based mobile/UI interactions.
    Designed to be extended with methods similar to WebTools (tap, type, screenshot).
    """

    def __init__(self, driver=None):
        self.driver = driver
