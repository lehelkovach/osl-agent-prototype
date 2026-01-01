import json

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient


def test_agent_creates_prototype_and_concept_via_ksg_tools():
    memory = MockMemoryTools()
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    # Plan: create prototype if missing, then concept
    fake_plan = json.dumps(
        {
            "intent": "remember",
            "steps": [
                {
                    "tool": "ksg.create_prototype",
                    "params": {
                        "name": "Person",
                        "description": "Prototype for person entities",
                        "context": "people",
                        "labels": ["Prototype", "Person"],
                        "embedding": [0.1, 0.2],
                    },
                    "comment": "Ensure Person prototype exists.",
                },
                {
                    "tool": "ksg.create_concept",
                    "params": {
                        "prototype_uuid": None,  # to be filled after prototype creation; test will monkey patch
                        "json_obj": {"name": "Lehel Kovach", "note": "User identity"},
                        "embedding": [0.3, 0.4],
                    },
                    "comment": "Create a person concept.",
                },
            ],
        }
    )
    fake_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.1, 0.2])
    agent = PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=builder,
        openai_client=fake_client,
    )

    # Monkey-patch to fill prototype_uuid after first tool
    original_execute_plan = agent._execute_plan

    def _patched(plan, prov):
        steps = plan.get("steps", [])
        for step in steps:
            if step.get("tool") == "ksg.create_concept" and step["params"].get("prototype_uuid") is None:
                # assume previous step created exactly one prototype
                proto_nodes = [n for n in memory.nodes.values() if n.kind == "Prototype"]
                if proto_nodes:
                    step["params"]["prototype_uuid"] = proto_nodes[0].uuid
        return original_execute_plan(plan, prov)

    agent._execute_plan = _patched  # type: ignore

    res = agent.execute_request("Remember and store a person concept")
    assert res["execution_results"]["status"] == "completed"
    protos = [n for n in memory.nodes.values() if n.kind == "Prototype"]
    concepts = [n for n in memory.nodes.values() if n.kind == "Concept"]
    assert protos and concepts
    assert concepts[0].props.get("prototype_uuid") == protos[0].uuid
