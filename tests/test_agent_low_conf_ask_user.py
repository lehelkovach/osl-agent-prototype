import pytest
from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools, MockContactsTools
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient


def make_agent():
    mem = MockMemoryTools()
    proc = ProcedureBuilder(mem, embed_fn=lambda text: [0.1, 0.2])
    agent = PersonalAssistantAgent(
        memory=mem,
        calendar=MockCalendarTools(),
        tasks=MockTaskTools(),
        contacts=MockContactsTools(),
        procedure_builder=proc,
        openai_client=FakeOpenAIClient(chat_response='{"intent":"inform","steps":[]}'),
    )
    return agent


def test_low_conf_inform_asks_user():
    agent = make_agent()
    result = agent.execute_request("how do I build a rocket?")
    assert result["execution_results"]["status"] == "ask_user"
    assert "instructions" in result["plan"]["raw_llm"].lower()
