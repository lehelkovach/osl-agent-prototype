import unittest

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


class SpyProcedureBuilder(ProcedureBuilder):
    def __init__(self, memory, embed_fn):
        super().__init__(memory, embed_fn)
        self.last_query = None
        self.search_called = False

    def search_procedures(self, query: str, top_k: int = 5):
        self.last_query = query
        self.search_called = True
        return [{"uuid": "proc-1", "props": {"title": "LinkedIn check"}}]


class TestAgentProcedureReuse(unittest.TestCase):
    def test_agent_recalls_procedure_before_planning(self):
        memory = MockMemoryTools()
        builder = SpyProcedureBuilder(memory, embed_fn=lambda text: [float(len(text)), 0.1])
        plan = """
        {
          "intent": "inform",
          "steps": []
        }
        """
        fake_client = FakeOpenAIClient(chat_response=plan, embedding=[0.1, 0.2])
        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            procedure_builder=builder,
            openai_client=fake_client,
        )

        agent.execute_request("check LinkedIn")
        self.assertTrue(builder.search_called)
        self.assertEqual(builder.last_query, "check LinkedIn")
        self.assertIsNotNone(agent._last_procedure_matches)
        self.assertGreaterEqual(len(agent._last_procedure_matches), 1)
        # Procedure matches should be included in LLM messages
        joined_msgs = " ".join(m["content"] for m in fake_client.last_messages or [])
        self.assertIn("Procedure matches", joined_msgs)

    def test_reuse_plan_when_llm_empty(self):
        memory = MockMemoryTools()
        builder = SpyProcedureBuilder(memory, embed_fn=lambda text: [float(len(text)), 0.1])
        fake_client = FakeOpenAIClient(chat_response='{"intent":"task","steps":[]}', embedding=[0.1, 0.2])
        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            procedure_builder=builder,
            openai_client=fake_client,
        )

        result = agent.execute_request("check LinkedIn")
        self.assertTrue(result["plan"].get("reuse", False))
        self.assertEqual(result["plan"]["steps"][0]["tool"], "procedure.search")

    def test_rag_query_event_contains_ts(self):
        memory = MockMemoryTools()
        builder = SpyProcedureBuilder(memory, embed_fn=lambda text: [float(len(text)), 0.1])
        fake_client = FakeOpenAIClient(chat_response='{"intent":"inform","steps":[]}', embedding=[0.1, 0.2])
        events = []

        class CollectBus:
            async def emit(self, event_type, payload):
                events.append((event_type, payload))

        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            procedure_builder=builder,
            openai_client=fake_client,
            event_bus=CollectBus(),
        )
        agent.execute_request("check LinkedIn")
        rag_events = [p for t, p in events if t == "rag_query"]
        self.assertGreaterEqual(len(rag_events), 1)
        self.assertIn("ts", rag_events[0])


if __name__ == "__main__":
    unittest.main()
