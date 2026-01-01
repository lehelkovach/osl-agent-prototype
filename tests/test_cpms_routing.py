import json
from datetime import datetime, timezone

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.cpms_adapter import CPMSAdapter


class StubCpmsClient:
    def __init__(self):
        self.created_procs = []
        self.list_calls = 0

    def create_procedure(self, name, description, steps):
        data = {"id": f"proc-{len(self.created_procs)+1}", "name": name, "description": description, "steps": steps}
        self.created_procs.append(data)
        return data

    def list_procedures(self):
        self.list_calls += 1
        return self.created_procs


def _agent(use_cpms: bool, cpms_client=None):
    mem = MockMemoryTools()
    proc = ProcedureBuilder(mem, embed_fn=lambda text: [0.1, 0.2])
    cpms = CPMSAdapter(cpms_client) if cpms_client else None
    agent = PersonalAssistantAgent(
        memory=mem,
        calendar=MockCalendarTools(),
        tasks=MockTaskTools(),
        contacts=MockContactsTools(),
        procedure_builder=proc,
        cpms=cpms,
        use_cpms_for_procs=use_cpms,
        openai_client=FakeOpenAIClient(chat_response=json.dumps({
            "intent": "inform",
            "steps": [
                {
                    "tool": "procedure.create",
                    "params": {"name": "Demo", "description": "desc", "steps": []},
                    "comment": "create via test",
                }
            ],
        })),
    )
    return agent, mem, cpms_client


def test_procedure_create_routes_to_cpms_when_flag_on():
    stub = StubCpmsClient()
    agent, _, _ = _agent(use_cpms=True, cpms_client=stub)
    result = agent.execute_request("create a procedure")
    assert result["execution_results"]["status"] == "completed"
    assert stub.created_procs, "CPMS should receive create_procedure"


def test_procedure_create_uses_local_builder_when_flag_off():
    stub = StubCpmsClient()
    agent, mem, _ = _agent(use_cpms=False, cpms_client=stub)
    result = agent.execute_request("create a procedure")
    assert result["execution_results"]["status"] == "completed"
    assert not stub.created_procs, "CPMS should not be called when flag is off"
    kinds = {n.kind for n in mem.nodes.values()}
    assert "Procedure" in kinds, "Local Procedure should be created via ProcedureBuilder"
