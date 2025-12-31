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


if __name__ == "__main__":
    unittest.main()
