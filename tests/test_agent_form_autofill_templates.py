import os
import json
from pathlib import Path

import pytest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
    MockWebTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.form_filler import FormDataRetriever
from src.personal_assistant.procedure_builder import ProcedureBuilder


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "forms"


def _make_agent(plan_json: dict, memory: MockMemoryTools):
    return PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        contacts=MockContactsTools(),
        web=MockWebTools(),
        procedure_builder=ProcedureBuilder(memory, embed_fn=lambda text: [0.1, 0.2]),
        openai_client=FakeOpenAIClient(chat_response=json.dumps(plan_json), embedding=[0.1, 0.2]),
    )


def test_autofill_billing_address():
    memory = MockMemoryTools()
    remember_plan = {
        "intent": "inform",
        "steps": [
            {
                "tool": "memory.remember",
                "params": {
                    "text": "Billing address for user",
                    "kind": "FormData",
                    "props": {
                        "givenName": "Ada",
                        "familyName": "Lovelace",
                        "address": "123 Code St",
                        "city": "London",
                        "state": "LN",
                        "postalCode": "SW1A",
                        "country": "UK",
                    },
                },
            }
        ],
    }
    agent = _make_agent(remember_plan, memory)
    agent.execute_request("remember my billing address")

    retriever = FormDataRetriever(memory)
    required = ["givenName", "familyName", "address", "city", "state", "postalCode", "country"]
    autofill = retriever.build_autofill(required_fields=required)
    for field in required:
        assert field in autofill


def test_autofill_credit_card():
    memory = MockMemoryTools()
    remember_plan = {
        "intent": "inform",
        "steps": [
            {
                "tool": "memory.remember",
                "params": {
                    "text": "Card info",
                    "kind": "PaymentMethod",
                    "props": {
                        "cardNumber": "4242 4242 4242 4242",
                        "cardExpiry": "12/30",
                        "cardCvv": "123",
                        "billingAddress": "123 Code St",
                    },
                },
            }
        ],
    }
    agent = _make_agent(remember_plan, memory)
    agent.execute_request("remember my credit card")

    retriever = FormDataRetriever(memory)
    required = ["cardNumber", "cardExpiry", "cardCvv", "billingAddress"]
    autofill = retriever.build_autofill(required_fields=required, query="Card info")
    for field in required:
        assert field in autofill


def test_autofill_login_credentials():
    memory = MockMemoryTools()
    remember_plan = {
        "intent": "inform",
        "steps": [
            {
                "tool": "memory.remember",
                "params": {
                    "text": "Login creds",
                    "kind": "Credential",
                    "props": {
                        "username": "user@example.com",
                        "password": "hunter2",
                    },
                },
            }
        ],
    }
    agent = _make_agent(remember_plan, memory)
    agent.execute_request("remember my login")

    retriever = FormDataRetriever(memory)
    autofill = retriever.build_autofill(required_fields=["username", "password"], query="Login creds")
    assert autofill["username"] == "user@example.com"
    assert autofill["password"] == "hunter2"


@pytest.mark.skipif(os.getenv("USE_PLAYWRIGHT", "0") not in ("1", "true", "yes"), reason="Playwright not enabled")
def test_playwright_fill_login_template():
    """
    Placeholder for a Playwright-backed test: ensure login template fields can be located and filled.
    Currently uses MockWebTools; replace with real PlaywrightWebTools when available.
    """
    memory = MockMemoryTools()
    remember_plan = {
        "intent": "inform",
        "steps": [
            {
                "tool": "memory.remember",
                "params": {
                    "text": "Login creds",
                    "kind": "Credential",
                    "props": {
                        "username": "user@example.com",
                        "password": "hunter2",
                    },
                },
            }
        ],
    }
    agent = _make_agent(remember_plan, memory)
    agent.execute_request("remember my login")

    # With real PlaywrightWebTools, we'd fetch DOM from the fixture and fill selectors.
    # For now, just assert we can build the autofill map.
    retriever = FormDataRetriever(memory)
    autofill = retriever.build_autofill(required_fields=["username", "password"], query="Login creds")
    assert "username" in autofill and "password" in autofill
