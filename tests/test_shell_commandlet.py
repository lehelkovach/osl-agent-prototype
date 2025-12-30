import unittest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
    MockShellTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient


class TestShellCommandlet(unittest.TestCase):
    def test_shell_run_staged_and_executes(self):
        fake_plan = """
        {
          "intent": "task",
          "steps": [
            {"tool": "shell.run", "params": {"command": "echo staged", "dry_run": true}},
            {"tool": "shell.run", "params": {"command": "echo real", "dry_run": false}}
          ]
        }
        """
        agent = PersonalAssistantAgent(
            memory=MockMemoryTools(),
            calendar=MockCalendarTools(),
            tasks=MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            shell=MockShellTools(),
            openai_client=FakeOpenAIClient(chat_response=fake_plan, embedding=[0.1, 0.1, 0.1]),
        )
        res = agent.execute_request("run shell commands")
        self.assertEqual(res["execution_results"]["status"], "completed")
        # history of shell calls
        shell_history = agent.shell.history
        self.assertEqual(len(shell_history), 2)
        self.assertEqual(shell_history[0]["status"], "staged")
        self.assertEqual(shell_history[1]["status"], "executed")


if __name__ == "__main__":
    unittest.main()
