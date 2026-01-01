import json
import random

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


def make_agent_with_plan(plan_json: dict, web=None):
    mem = MockMemoryTools()
    proc = ProcedureBuilder(mem, embed_fn=lambda text: [0.1, 0.2])
    agent = PersonalAssistantAgent(
        memory=mem,
        calendar=MockCalendarTools(),
        tasks=MockTaskTools(),
        contacts=MockContactsTools(),
        web=web,
        procedure_builder=proc,
        openai_client=FakeOpenAIClient(chat_response=json.dumps(plan_json)),
    )
    return agent


def test_webform_fill_and_submit_when_fields_present():
    web = MockWebTools()
    plan = {
        "intent": "inform",
        "steps": [
            {"tool": "web.fill", "params": {"url": "http://form.local", "selector": "#user", "text": "alice"}},
            {"tool": "web.fill", "params": {"url": "http://form.local", "selector": "#pass", "text": "secret"}},
            {"tool": "web.click_selector", "params": {"url": "http://form.local", "selector": "#submit"}},
        ],
    }
    agent = make_agent_with_plan(plan, web=web)
    result = agent.execute_request("please submit this form")
    assert result["execution_results"]["status"] == "completed"
    methods = [h["method"] for h in web.history]
    assert "FILL" in methods and "CLICK_SELECTOR" in methods


def test_webform_missing_fields_causes_ask_user():
    # Simulate LLM low-confidence by returning no steps
    plan = {"intent": "inform", "steps": []}
    agent = make_agent_with_plan(plan, web=MockWebTools())
    result = agent.execute_request("please submit this form but fields unknown")
    assert result["execution_results"]["status"] == "ask_user"
