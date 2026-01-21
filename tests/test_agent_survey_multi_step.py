import json

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
)
from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.openai_client import FakeOpenAIClient


class MultiStepWebTools:
    def __init__(self):
        self.page_index = 0
        self.history = []

    def get_dom(self, url: str, session_id=None):
        if self.page_index == 0:
            html = """
            <form>
              <input id="birth_month" name="birth_month" required />
              <input id="birth_day" name="birth_day" required />
              <input id="birth_year" name="birth_year" required />
              <button id="continue">Continue</button>
            </form>
            """
        else:
            html = """
            <form>
              <input id="zip_code" name="zip_code" required />
              <button id="finish">Finish</button>
            </form>
            """
        return {"status": 200, "url": url, "html": html, "screenshot_path": None}

    def fill(self, url: str, selector: str, text: str, session_id=None):
        self.history.append({"method": "FILL", "selector": selector, "text": text})
        return {"status": 200, "url": url, "selector": selector, "text": text}

    def click_selector(self, url: str, selector: str, session_id=None):
        self.history.append({"method": "CLICK_SELECTOR", "selector": selector})
        if selector == "#continue" and self.page_index == 0:
            self.page_index = 1
        elif selector == "#finish":
            self.page_index = 2
        return {"status": 200, "url": url, "selector": selector, "clicked": True}

    def get(self, url: str, session_id=None):
        return {"status": 200, "url": url}

    def post(self, url: str, payload: dict, session_id=None):
        return {"status": 200, "url": url}

    def screenshot(self, url: str, session_id=None):
        return {"status": 200, "url": url}

    def locate_bounding_box(self, url: str, query: str, session_id=None):
        return {"status": 200, "url": url}

    def click_xy(self, url: str, x: int, y: int, session_id=None):
        return {"status": 200, "url": url}

    def click_xpath(self, url: str, xpath: str, session_id=None):
        return {"status": 200, "url": url}

    def wait_for(self, url: str, selector: str, timeout_ms: int = 5000, session_id=None):
        return {"status": 200, "url": url}

    def close_session(self, session_id: str):
        return {"status": "success", "session_id": session_id}


def _make_agent(web_tools, memory):
    plan = {
        "intent": "inform",
        "steps": [
            {
                "tool": "survey.fill_multi_step",
                "params": {
                    "url": "https://example.com/survey",
                    "continue_selector": "#continue",
                    "finish_selectors": ["#finish"],
                    "confidence_threshold": 0.9,
                },
            }
        ],
    }
    return PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=web_tools,
        contacts=MockContactsTools(),
        openai_client=FakeOpenAIClient(chat_response=json.dumps(plan), embedding=[0.1, 0.2]),
    )


def test_multi_step_survey_fills_and_finishes():
    memory = MockMemoryTools()
    prov = Provenance("user", "2026-01-01T00:00:00Z", 1.0, "trace")
    identity = Node(
        kind="Identity",
        labels=["Identity"],
        props={
            "birth_month": "01",
            "birth_day": "02",
            "birth_year": "1990",
            "zip_code": "12345",
        },
    )
    memory.upsert(identity, prov)
    web = MultiStepWebTools()
    agent = _make_agent(web, memory)

    res = agent.execute_request("fill multi-step survey")
    step = res["execution_results"]["steps"][0]
    assert step["status"] == "success"
    assert step["pages_completed"] == 2
    methods = [h["method"] for h in web.history]
    assert methods.count("FILL") == 4
    assert "CLICK_SELECTOR" in methods


def test_multi_step_survey_prompts_on_missing():
    memory = MockMemoryTools()
    web = MultiStepWebTools()
    agent = _make_agent(web, memory)

    res = agent.execute_request("fill multi-step survey")
    step = res["execution_results"]["steps"][0]
    assert step["status"] == "ask_user"
    assert "birth" in step.get("prompt", "").lower()
