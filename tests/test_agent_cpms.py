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


if __name__ == "__main__":
    unittest.main()
