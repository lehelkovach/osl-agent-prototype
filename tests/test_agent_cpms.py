import unittest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.cpms_adapter import CPMSAdapter
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient


class FakeCpmsClient:
    def __init__(self):
        self.procedures = {}
        self.tasks = {}

    def create_procedure(self, name, description, steps):
        proc_id = f"proc-{len(self.procedures)+1}"
        data = {"id": proc_id, "name": name, "description": description, "steps": steps}
        self.procedures[proc_id] = data
        return data

    def list_procedures(self):
        return list(self.procedures.values())

    def get_procedure(self, procedure_id):
        return self.procedures[procedure_id]

    def create_task(self, procedure_id, title, payload):
        task_id = f"task-{len(self.tasks)+1}"
        data = {"id": task_id, "procedure_id": procedure_id, "title": title, "payload": payload}
        self.tasks[task_id] = data
        return data

    def list_tasks(self, procedure_id=None):
        if procedure_id:
            return [t for t in self.tasks.values() if t["procedure_id"] == procedure_id]
        return list(self.tasks.values())


class TestAgentCPMS(unittest.TestCase):
    def test_cpms_procedure_and_task_flow(self):
        memory = MockMemoryTools()
        cpms_client = FakeCpmsClient()
        cpms_adapter = CPMSAdapter(cpms_client)
        plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "cpms.create_procedure",
              "params": {
                "name": "LinkedIn follow-up",
                "description": "Check recruiter messages and respond",
                "steps": [{"name": "open messages"}]
              }
            },
            {
              "tool": "cpms.list_procedures",
              "params": {}
            },
            {
              "tool": "cpms.create_task",
              "params": {
                "procedure_id": "proc-1",
                "title": "Respond to recruiter",
                "payload": {"channel": "linkedin"}
              }
            },
            {
              "tool": "cpms.list_tasks",
              "params": {"procedure_id": "proc-1"}
            }
          ]
        }
        """
        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            cpms=cpms_adapter,
            openai_client=FakeOpenAIClient(chat_response=plan, embedding=[0.1, 0.1, 0.1]),
        )

        result = agent.execute_request("manage cpms procedures")
        self.assertEqual(result["execution_results"]["status"], "completed")
        # Procedure was created
        self.assertEqual(len(cpms_client.procedures), 1)
        self.assertEqual(cpms_client.procedures["proc-1"]["name"], "LinkedIn follow-up")
        # Task was created and linked
        self.assertEqual(len(cpms_client.tasks), 1)
        task = next(iter(cpms_client.tasks.values()))
        self.assertEqual(task["procedure_id"], "proc-1")
        # Agent returned procedure list
        step_results = result["execution_results"]["steps"]
        procedures_step = next(s for s in step_results if "procedures" in s)
        self.assertEqual(len(procedures_step["procedures"]), 1)

    def test_cpms_detect_form_can_store_pattern_into_ksg_when_enabled(self):
        """
        If USE_CPMS_FOR_FORMS is enabled, cpms.detect_form should store the detected
        pattern in KnowShowGo and (optionally) link it to a parent concept.
        """
        memory = MockMemoryTools()
        cpms_client = FakeCpmsClient()

        # Provide detect_form() on the fake CPMS client.
        def _detect_form(html, screenshot_path=None, screenshot=None, url=None, dom_snapshot=None, observation=None):
            return {
                "form_type": "login",
                "fields": [{"type": "email", "selector": "input[type='email']", "confidence": 0.9}],
                "confidence": 0.85,
                "pattern_id": "p-1",
            }

        cpms_client.detect_form = _detect_form  # type: ignore[attr-defined]
        cpms_adapter = CPMSAdapter(cpms_client)

        # Create a parent concept to link patterns to.
        prov = Provenance(source="user", ts="2026-01-01T00:00:00Z", confidence=1.0, trace_id="t")
        parent = Node(kind="Concept", labels=["Test"], props={"name": "ExampleSite"})
        memory.upsert(parent, prov, embedding_request=False)

        plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "cpms.detect_form",
              "params": {
                "html": "<form><input type=\\"email\\"></form>",
                "url": "https://example.com/login",
                "concept_uuid": "%s",
                "pattern_name": "example.com:login"
              }
            }
          ]
        }
        """ % parent.uuid

        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            cpms=cpms_adapter,
            use_cpms_for_forms=True,
            openai_client=FakeOpenAIClient(chat_response=plan, embedding=[0.1, 0.1, 0.1]),
        )

        result = agent.execute_request("detect a form and store it")
        self.assertEqual(result["execution_results"]["status"], "completed")

        # Ensure at least one stored Pattern concept exists.
        pattern_nodes = [
            n for n in memory.nodes.values()
            if n.kind == "Concept" and n.props.get("source") == "cpms" and "pattern_data" in n.props
        ]
        self.assertTrue(pattern_nodes, "Expected a stored CPMS Pattern concept")

        # Ensure a has_pattern edge exists from the parent concept to the stored pattern.
        has_pattern_edges = [
            e for e in memory.edges.values()
            if e.rel == "has_pattern" and e.from_node == parent.uuid
        ]
        self.assertTrue(has_pattern_edges, "Expected parent -> pattern has_pattern edge")


if __name__ == "__main__":
    unittest.main()
