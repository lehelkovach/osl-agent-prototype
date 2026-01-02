from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
    MockWebTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.models import Provenance


class DummyCPMS:
    def __init__(self):
        self.called = 0
        self.last_params = None

    def create_procedure(self, **params):
        self.called += 1
        self.last_params = params
        return {"id": "cpms-proc"}


def _make_agent(use_cpms: bool, cpms_adapter=None):
    memory = MockMemoryTools()
    return PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        contacts=MockContactsTools(),
        web=MockWebTools(),
        procedure_builder=ProcedureBuilder(memory, embed_fn=lambda text: [0.1, 0.2]),
        openai_client=FakeOpenAIClient(chat_response='{"intent":"inform","steps": []}', embedding=[0.1, 0.2]),
        cpms=cpms_adapter,
        use_cpms_for_procs=use_cpms,
    )


def test_procedure_create_routes_to_cpms_when_enabled():
    dummy = DummyCPMS()
    agent = _make_agent(use_cpms=True, cpms_adapter=dummy)
    plan = {
        "intent": "task",
        "steps": [
            {"tool": "procedure.create", "params": {"title": "Via CPMS", "description": "desc", "steps": []}},
        ],
    }

    res = agent._execute_plan(plan, Provenance(source="user", ts="now", confidence=1.0, trace_id="t1"))

    assert res["status"] == "completed"
    assert dummy.called == 1
    assert res["steps"][0]["procedure"]["id"] == "cpms-proc"


def test_procedure_create_uses_builder_when_cpms_disabled():
    dummy = DummyCPMS()
    agent = _make_agent(use_cpms=False, cpms_adapter=dummy)
    plan = {
        "intent": "task",
        "steps": [
            {"tool": "procedure.create", "params": {"title": "Via Builder", "description": "desc", "steps": []}},
        ],
    }

    res = agent._execute_plan(plan, Provenance(source="user", ts="now", confidence=1.0, trace_id="t2"))

    assert res["status"] == "completed"
    assert dummy.called == 0
    assert "procedure_uuid" in res["steps"][0]["procedure"]
