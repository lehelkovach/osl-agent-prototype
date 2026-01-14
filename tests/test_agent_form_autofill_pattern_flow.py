import unittest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.cpms_adapter import CPMSAdapter
from src.personal_assistant.form_fingerprint import compute_form_fingerprint
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.models import Node, Provenance


class _CpmsClientNeverCalled:
    def detect_form(self, *_args, **_kwargs):
        raise AssertionError("CPMS detect_form should not be called when reuse succeeds")


class _CpmsClientReturnsLogin:
    def detect_form(self, html, screenshot_path=None, screenshot=None, url=None, dom_snapshot=None, observation=None):
        return {
            "form_type": "login",
            "fields": [
                {"type": "username", "selector": "#user", "confidence": 0.9},
                {"type": "password", "selector": "#pass", "confidence": 0.9},
                {"type": "submit", "selector": "#submit", "confidence": 0.8},
            ],
            "confidence": 0.9,
            "pattern_id": "p-1",
        }


class TestAutofillPatternFlow(unittest.TestCase):
    def test_autofill_reuses_stored_pattern_without_cpms(self):
        memory = MockMemoryTools()
        prov = Provenance("user", "2026-01-01T00:00:00Z", 1.0, "t")
        web = MockWebTools()
        url = "https://example.com/login"

        # Store dataset values in memory.
        form_node = Node(kind="FormData", labels=["vault"], props={"username": "ada", "password": "hunter2"})
        memory.upsert(form_node, prov)

        # Pre-store a CPMS pattern concept that matches the DOM fingerprint from MockWebTools.get_dom().
        dom = web.get_dom(url)
        html = dom["html"]
        fp = compute_form_fingerprint(url=url, html=html).to_dict()
        pattern_concept = Node(
            kind="Concept",
            labels=["Pattern", "example.com:login"],
            props={
                "name": "example.com:login",
                "source": "cpms",
                "pattern_data": {
                    "form_type": "login",
                    "fields": [
                        {"type": "username", "selector": "#user", "confidence": 0.9},
                        {"type": "password", "selector": "#pass", "confidence": 0.9},
                    ],
                    "confidence": 0.9,
                    "fingerprint": fp,
                },
            },
        )
        memory.upsert(pattern_concept, prov, embedding_request=False)

        plan = """
        {
          "intent": "inform",
          "steps": [
            {
              "tool": "form.autofill",
              "params": {
                "url": "%s",
                "form_type": "login",
                "reuse_min_score": 2.0
              }
            }
          ]
        }
        """ % url

        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=web,
            contacts=MockContactsTools(),
            cpms=CPMSAdapter(_CpmsClientNeverCalled()),
            use_cpms_for_forms=True,
            openai_client=FakeOpenAIClient(chat_response=plan, embedding=[0.2, 0.1]),
        )

        res = agent.execute_request("autofill login")
        self.assertEqual(res["execution_results"]["status"], "completed")
        step = res["execution_results"]["steps"][0]
        self.assertEqual(step["status"], "success")
        self.assertTrue(step.get("reused"))
        self.assertEqual(step.get("pattern_uuid"), pattern_concept.uuid)

        fills = [h for h in web.history if h.get("method") == "FILL"]
        self.assertEqual(len(fills), 2)
        values = {f["selector"]: f["text"] for f in fills}
        self.assertEqual(values["#user"], "ada")
        self.assertEqual(values["#pass"], "hunter2")

    def test_autofill_falls_back_to_cpms_and_stores_pattern(self):
        memory = MockMemoryTools()
        prov = Provenance("user", "2026-01-01T00:00:00Z", 1.0, "t")
        web = MockWebTools()
        url = "https://example.com/login"

        # Store dataset values in memory.
        form_node = Node(kind="FormData", labels=["vault"], props={"username": "ada", "password": "hunter2"})
        memory.upsert(form_node, prov)

        plan = """
        {
          "intent": "inform",
          "steps": [
            {
              "tool": "form.autofill",
              "params": {
                "url": "%s",
                "form_type": "login",
                "reuse_min_score": 10.0
              }
            }
          ]
        }
        """ % url

        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=web,
            contacts=MockContactsTools(),
            cpms=CPMSAdapter(_CpmsClientReturnsLogin()),
            use_cpms_for_forms=True,
            openai_client=FakeOpenAIClient(chat_response=plan, embedding=[0.2, 0.1]),
        )

        res = agent.execute_request("autofill login")
        self.assertEqual(res["execution_results"]["status"], "completed")
        step = res["execution_results"]["steps"][0]
        self.assertEqual(step["status"], "success")
        self.assertFalse(step.get("reused", False))
        self.assertIn("pattern_uuid", step)

        # Ensure a stored CPMS Pattern concept exists.
        pattern_nodes = [
            n for n in memory.nodes.values()
            if n.kind == "Concept" and n.props.get("source") == "cpms" and "pattern_data" in n.props
        ]
        self.assertTrue(pattern_nodes)

        fills = [h for h in web.history if h.get("method") == "FILL"]
        self.assertEqual(len(fills), 2)


if __name__ == "__main__":
    unittest.main()

