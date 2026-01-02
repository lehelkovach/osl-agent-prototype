import json
from datetime import datetime, timezone

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
    MockWebTools,
    MockShellTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.procedure_builder import ProcedureBuilder


def _make_agent(plan_json: dict, memory: MockMemoryTools) -> PersonalAssistantAgent:
    return PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        contacts=MockContactsTools(),
        web=MockWebTools(),
        shell=MockShellTools(),
        procedure_builder=ProcedureBuilder(memory, embed_fn=lambda text: [0.1, 0.2]),
        openai_client=FakeOpenAIClient(chat_response=json.dumps(plan_json), embedding=[0.1, 0.2]),
    )


def test_queue_enqueue_with_delay_seconds():
    memory = MockMemoryTools()
    plan = {
        "intent": "task",
        "steps": [
            {
                "tool": "queue.enqueue",
                "params": {"title": "Delayed task", "priority": 1, "delay_seconds": 60},
            }
        ],
    }
    agent = _make_agent(plan, memory)
    agent.execute_request("schedule something soon")

    queue = agent.queue_manager.queue_node
    item = queue.props["items"][0]
    assert item["title"] == "Delayed task"
    assert item["priority"] == 1
    assert item["status"] == "pending"
    nb = item.get("not_before")
    assert nb is not None
    nb_dt = datetime.fromisoformat(nb.replace("Z", "+00:00"))
    assert nb_dt > datetime.now(timezone.utc)
