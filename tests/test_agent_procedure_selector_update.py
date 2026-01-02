import json

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.models import Provenance


class FallbackWebTools:
    """
    Fails on first selector (#username), succeeds on any other selector.
    """

    def __init__(self):
        self.history = []

    def fill(self, url: str, selector: str, text: str):
        if selector == "#username":
            raise RuntimeError("selector not found")
        res = {"status": 200, "url": url, "selector": selector, "text": text}
        self.history.append(res)
        return res

    def get(self, **kwargs):
        return {"status": 200}

    def post(self, **kwargs):
        return {"status": 200}

    def screenshot(self, **kwargs):
        return {"status": 200}

    def get_dom(self, **kwargs):
        return {"status": 200}

    def locate_bounding_box(self, **kwargs):
        return {"status": 200}

    def click_selector(self, **kwargs):
        return {"status": 200}

    def click_xpath(self, **kwargs):
        return {"status": 200}

    def click_xy(self, **kwargs):
        return {"status": 200}

    def wait_for(self, **kwargs):
        return {"status": 200}


def test_fallback_selector_persists_into_procedure():
    memory = MockMemoryTools()
    prov = Provenance(source="user", ts="now", confidence=1.0, trace_id="proc-sel")
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [0.1, 0.2])
    proc = builder.create_procedure(
        title="Login Stored",
        description="Stored login",
        steps=[
            {
                "title": "web.fill",
                "tool": "web.fill",
                "payload": {
                    "tool": "web.fill",
                    "params": {
                        "url": "http://x",
                        "selectors": {"username": "#username"},
                        "values": {"username": "alice"},
                    },
                },
            }
        ],
        provenance=prov,
    )

    plan = {
        "intent": "web_io",
        "procedure_uuid": proc["procedure_uuid"],
        "steps": [
            {
                "tool": "web.fill",
                "params": {
                    "url": "http://x",
                    "selectors": {"username": "#username"},
                    "values": {"username": "alice"},
                },
            }
        ],
    }
    agent = PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=FallbackWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=builder,
        openai_client=FakeOpenAIClient(chat_response=json.dumps(plan), embedding=[0.1, 0.2]),
    )

    res = agent.execute_request("Run stored login")
    assert res["execution_results"]["status"] == "completed"

    # Step should be updated to use the fallback selector (input[type='email'] or text)
    steps = memory.search("", top_k=10, filters={"kind": "Step"}, query_embedding=None)
    sel_values = []
    for st in steps:
        if st.get("props", {}).get("procedure_uuid") == proc["procedure_uuid"]:
            payload = st.get("props", {}).get("payload", {})
            params = payload.get("params", {})
            selectors = params.get("selectors", {})
            sel_values.append(selectors.get("username"))
    assert any(s != "#username" for s in sel_values)
