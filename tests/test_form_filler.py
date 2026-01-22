import unittest

from src.personal_assistant.form_filler import FormDataRetriever
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Node, Provenance


class TestFormFiller(unittest.TestCase):
    def test_autofill_from_formdata(self):
        memory = MockMemoryTools()
        prov = Provenance("user", "2024-01-01T00:00:00Z", 1.0, "trace")
        form_node = Node(
            kind="FormData",
            labels=["vault"],
            props={
                "givenName": "Ada",
                "familyName": "Lovelace",
                "address": "123 Code St",
                "city": "London",
                "postalCode": "SW1A",
                "country": "UK",
                "username": "ada",
                "password": "p@ss",
            },
        )
        memory.upsert(form_node, prov)
        retriever = FormDataRetriever(memory)
        required = ["givenName", "familyName", "address", "postalCode", "country", "username", "password"]
        fill = retriever.build_autofill(required_fields=required)
        for f in required:
            self.assertIn(f, fill)
        self.assertEqual(fill["givenName"], "Ada")
        self.assertEqual(fill["password"], "p@ss")


class TestFormTypeDatasetSelection(unittest.TestCase):
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
        self.prov = Provenance("user", "2024-01-01T00:00:00Z", 1.0, "trace")

    def test_login_prefers_credentials_over_formdata(self):
        cred_node = Node(
            kind="Credential",
            labels=["Credential"],
            props={"domain": "example.com", "username": "cred_user", "password": "cred_pass"},
        )
        form_node = Node(
            kind="FormData",
            labels=["FormData"],
            props={"username": "form_user", "password": "form_pass"},
        )
        self.memory.upsert(form_node, self.prov)
        self.memory.upsert(cred_node, self.prov)

        result = self.retriever.collect_values_for_form(
            required_fields=["username", "password"],
            form_type="login",
            url="https://example.com/login",
        )

        values = result["values"]
        sources = result["sources"]
        self.assertEqual(values.get("username"), "cred_user")
        self.assertEqual(values.get("password"), "cred_pass")
        self.assertEqual(sources.get("username"), "Credential")

    def test_billing_prefers_payment_method_and_identity(self):
        payment = Node(
            kind="PaymentMethod",
            labels=["PaymentMethod"],
            props={"card_number": "4111111111111111", "expiry": "12/30", "cvv": "123", "is_valid": True},
        )
        identity = Node(
            kind="Identity",
            labels=["Identity"],
            props={"full_name": "Ada Lovelace", "address": "123 Code St"},
        )
        self.memory.upsert(payment, self.prov)
        self.memory.upsert(identity, self.prov)

        result = self.retriever.collect_values_for_form(
            required_fields=["card_number", "expiry", "cvv", "full_name", "address"],
            form_type="billing",
            url="https://shop.example.com/checkout",
        )

        values = result["values"]
        sources = result["sources"]
        self.assertEqual(values.get("card_number"), "4111111111111111")
        self.assertEqual(values.get("expiry"), "12/30")
        self.assertEqual(values.get("full_name"), "Ada Lovelace")
        self.assertEqual(sources.get("card_number"), "PaymentMethod")
        self.assertEqual(sources.get("full_name"), "Identity")


class TestLoginResultDetection(unittest.TestCase):
    def setUp(self):
        self.retriever = FormDataRetriever(MockMemoryTools())

    def test_detect_login_success(self):
        result = self.retriever.detect_login_result(
            page_text="Welcome back! You are now signed in.",
            page_html="<div>Sign out</div>",
        )
        self.assertEqual(result["status"], "success")

    def test_detect_login_failure(self):
        result = self.retriever.detect_login_result(
            page_text="Invalid password. Please try again.",
            page_html="<form><input type='password'></form>",
        )
        self.assertEqual(result["status"], "failed")

if __name__ == "__main__":
    unittest.main()
