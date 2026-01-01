import json
import os

import pytest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient, OpenAIClient
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.prompts import SYSTEM_PROMPT, DEVELOPER_PROMPT


def test_llm_returns_valid_json_command_and_is_parsed():
    fake_plan = json.dumps(
        {
            "commandtype": "procedure",
            "metadata": {
                "message_type": "command",
                "format": "json",
                "steps": [
                    {
                        "commandtype": "web.get",
                        "metadata": {"url": "http://example.com"},
                        "comment": "dummy step",
                    }
                ],
            },
        }
    )
    fake_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.1, 0.2, 0.3])
    memory = MockMemoryTools()
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    agent = PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=builder,
        openai_client=fake_client,
    )

    res = agent.execute_request("respond with a dummy procedure command")

    # Verify response_format enforced and parsed steps executed
    assert fake_client.last_response_format == {"type": "json_object"}
    assert fake_client.last_temperature == 0.0
    assert res["plan"]["steps"][0]["tool"] == "web.get"
    assert res["execution_results"]["status"] == "completed"

    # Ensure prompt wiring includes system + developer prompts up front
    assert fake_client.last_messages[0]["content"] == SYSTEM_PROMPT
    assert fake_client.last_messages[1]["content"] == DEVELOPER_PROMPT


@pytest.mark.skipif(
    os.getenv("LIVE_OPENAI_JSON_TEST", "0").lower() not in ("1", "true", "yes"),
    reason="Set LIVE_OPENAI_JSON_TEST=1 to exercise live OpenAI JSON parsing",
)
def test_live_openai_json_response_format():
    """Smoke test: ensure response_format=json_object yields parseable JSON with steps."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    client = OpenAIClient()
    messages = [
        {
            "role": "system",
            "content": (
                "Return ONLY a JSON object. Do not wrap in markdown. "
                "Include either intent+steps or commandtype+metadata.steps. "
                "Each step should be a web.get to http://example.com with a comment."
            ),
        },
        {
            "role": "user",
            "content": "Respond with a dummy procedure command.",
        },
    ]
    resp = client.chat(messages, temperature=0.0, response_format={"type": "json_object"})
    obj = json.loads(resp)
    assert isinstance(obj, dict)
    steps = obj.get("steps") or obj.get("metadata", {}).get("steps")
    assert isinstance(steps, list) and len(steps) >= 1
