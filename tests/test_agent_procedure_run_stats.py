import json

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.procedure_builder import ProcedureBuilder


def test_procedure_run_persists_stats_and_links():
    memory = MockMemoryTools()
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [float(len(text)), 0.1])
    # Force a simple plan that executes a web.get (handled by MockWebTools)
    plan = {
        "commandtype": "procedure",
        "metadata": {
            "steps": [
                {"commandtype": "web.get", "metadata": {"url": "http://example.com"}},
            ]
        },
    }
    fake_plan = json.dumps(plan)
    agent = PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=builder,
        openai_client=FakeOpenAIClient(chat_response=fake_plan, embedding=[0.2, 0.1]),
    )

    res = agent.execute_request("do a web get")
    assert res["execution_results"]["status"] == "completed"

    # One procedure should have been created with tested/success_count metadata
    procs = [n for n in memory.nodes.values() if n.kind == "Procedure"]
    assert len(procs) == 1
    proc = procs[0]
    assert proc.props.get("tested") is True
    assert proc.props.get("success_count") == 1
    assert proc.props.get("failure_count") == 0

    # A ProcedureRun should exist and be linked to the procedure
    runs = [n for n in memory.nodes.values() if n.kind == "ProcedureRun"]
    assert len(runs) == 1
    run = runs[0]
    links = [e for e in memory.edges.values() if e.rel == "run_of" and e.from_node == run.uuid]
    assert len(links) == 1
    assert links[0].to_node == proc.uuid
