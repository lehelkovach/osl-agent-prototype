import unittest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import MockCalendarTools, MockTaskTools, MockWebTools, MockContactsTools
from src.personal_assistant.models import Node
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.task_queue import TaskQueueManager
from src.personal_assistant.mock_tools import MockMemoryTools


class SpyMemoryTools(MockMemoryTools):
    """MockMemoryTools that records search inputs/outputs for verification."""

    def __init__(self):
        super().__init__()
        self.last_query_embedding = None
        self.last_query_text = None
        self.last_results = None

    def search(self, query_text, top_k, filters=None, query_embedding=None):
        if query_embedding is not None:
            self.last_query_embedding = query_embedding
        self.last_query_text = query_text
        results = super().search(query_text, top_k, filters, query_embedding)
        if query_embedding is not None:
            self.last_results = results
        return results


class TestSemanticMemoryIntegration(unittest.TestCase):
    def test_agent_queries_and_upserts_with_embeddings(self):
        # Seed memory with two concepts for retrieval scoring
        memory = SpyMemoryTools()
        concept_a = Node(kind="Concept", labels=["a"], props={"name": "alpha"}, llm_embedding=[0.9, 0.0, 0.0])
        concept_b = Node(kind="Concept", labels=["b"], props={"name": "beta"}, llm_embedding=[0.0, 0.9, 0.0])
        memory.upsert(concept_a, provenance=None)  # provenance unused in mock
        memory.upsert(concept_b, provenance=None)

        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        contacts = MockContactsTools()

        fake_plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "tasks.create",
              "params": {
                "title": "semantic task",
                "due": null,
                "priority": 1,
                "notes": "Created for semantic memory test",
                "links": []
              }
            }
          ]
        }
        """
        embed_vec = [0.9, 0.0, 0.0]
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=embed_vec)
        agent = PersonalAssistantAgent(
            memory,
            calendar,
            tasks,
            web=web,
            contacts=contacts,
            openai_client=openai_client,
        )

        result = agent.execute_request("remember alpha concept")

        # Agent should have queried memory with the embedding from the fake client
        self.assertEqual(memory.last_query_embedding, embed_vec)
        # The closest concept should be the alpha concept
        self.assertIsNotNone(memory.last_results)
        self.assertGreaterEqual(len(memory.last_results), 1)
        self.assertEqual(memory.last_results[0]["uuid"], concept_a.uuid)

        # A task node was upserted with the same embedding
        task_nodes = [n for n in memory.nodes.values() if n.kind == "Task"]
        self.assertEqual(len(task_nodes), 1)
        self.assertEqual(task_nodes[0].props["title"], "semantic task")
        self.assertEqual(task_nodes[0].llm_embedding, embed_vec)

        # The plan executed successfully
        self.assertEqual(result["plan"]["intent"], "task")
        self.assertEqual(result["execution_results"]["status"], "completed")

    def test_fact_persisted_and_retrieved_after_restart(self):
        # Phase 1: user tells a fact; agent stores it as a concept with embedding
        memory = SpyMemoryTools()
        fact_plan = """
        {
          "intent": "remember",
          "steps": [
            {
              "tool": "memory.remember",
              "params": {
                "text": "I live in Paris",
                "kind": "Person",
                "labels": ["fact", "profile"]
              }
            }
          ]
        }
        """
        embed_vec = [0.4, 0.1, 0.0]
        agent1 = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            openai_client=FakeOpenAIClient(chat_response=fact_plan, embedding=embed_vec),
        )
        agent1.execute_request("remember that I live in Paris")
        fact_nodes = [n for n in memory.nodes.values() if n.props.get("content") == "I live in Paris"]
        self.assertEqual(len(fact_nodes), 1)
        self.assertEqual(fact_nodes[0].llm_embedding, embed_vec)

        # Phase 2: simulate a restart with a new agent over the same memory; ensure retrieval hits the fact
        agent2 = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            openai_client=FakeOpenAIClient(chat_response='{"intent":"inform","steps":[]}', embedding=embed_vec),
        )
        agent2.execute_request("where do I live?")
        self.assertEqual(memory.last_query_embedding, embed_vec)
        self.assertIsNotNone(memory.last_results)
        self.assertGreaterEqual(len(memory.last_results), 1)
        self.assertTrue(any(r["uuid"] == fact_nodes[0].uuid for r in memory.last_results))


if __name__ == "__main__":
    unittest.main()
