import unittest
from datetime import datetime

from src.personal_assistant.models import Provenance, Node
from src.personal_assistant.mock_tools import MockMemoryTools, MockContactsTools


class TestContacts(unittest.TestCase):
    def setUp(self):
        self.memory = MockMemoryTools()
        self.contacts = MockContactsTools()
        self.provenance = Provenance("user", datetime.utcnow().isoformat(), 1.0, "trace-contacts")

    def test_create_and_list_contacts(self):
        res = self.contacts.create(
            name="Ada Lovelace",
            emails=["ada@example.com"],
            phones=["+1-111-111-1111"],
            org="Analytical Engines",
            notes="Pioneer",
            tags=["vip", "engineering"],
        )
        self.assertEqual(res["status"], "success")
        listed = self.contacts.list()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "Ada Lovelace")
        filtered = self.contacts.list({"org": "Analytical Engines"})
        self.assertEqual(len(filtered), 1)


if __name__ == "__main__":
    unittest.main()
