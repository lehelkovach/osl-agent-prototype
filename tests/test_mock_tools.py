import unittest
from datetime import datetime
from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools, MockWebTools

class TestMockTools(unittest.TestCase):

    def setUp(self):
        """Set up mock tools for each test."""
        self.memory = MockMemoryTools()
        self.calendar = MockCalendarTools()
        self.tasks = MockTaskTools()
        self.provenance = Provenance("user", datetime.utcnow().isoformat(), 1.0, "trace-1")

    def test_memory_upsert_and_search(self):
        """Test that a node can be upserted and then searched for."""
        node = Node(kind="Concept", labels=["test"], props={"name": "Test Concept"})
        self.memory.upsert(node, self.provenance)
        
        self.assertIn(node.uuid, self.memory.nodes)
        
        results = self.memory.search("Test Concept", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['uuid'], node.uuid)

    def test_calendar_create_and_list(self):
        """Test that a calendar event can be created and then listed."""
        self.calendar.create_event(
            title="Test Event",
            start="2025-12-29T10:00:00Z",
            end="2025-12-29T11:00:00Z",
            attendees=["test@example.com"],
            location="Test Location",
            notes="Test notes."
        )
        
        events = self.calendar.list({"start": "2025-12-29", "end": "2025-12-30"})
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], "Test Event")

    def test_tasks_create_and_list(self):
        """Test that a task can be created and then listed."""
        self.tasks.create(
            title="Test Task",
            due="2025-12-31",
            priority=1,
            notes="Finish testing.",
            links=[]
        )
        
        tasks = self.tasks.list()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['title'], "Test Task")
        self.assertEqual(tasks[0]['status'], "pending")

    def test_web_tools(self):
        """Test basic mock web tools flows."""
        web = MockWebTools()
        res_get = web.get("https://example.com")
        res_post = web.post("https://example.com/api", {"foo": "bar"})
        res_shot = web.screenshot("https://example.com")
        res_click = web.click_selector("https://example.com", "#login")
        res_dom = web.get_dom("https://example.com")
        res_xpath = web.click_xpath("https://example.com", "//button[@id='ok']")

        self.assertEqual(res_get["status"], 200)
        self.assertEqual(res_post["status"], 200)
        self.assertEqual(res_shot["status"], 200)
        self.assertEqual(res_click["action"], "click_selector")
        self.assertEqual(res_dom["status"], 200)
        self.assertIn("html", res_dom)
        self.assertIn("screenshot_base64", res_dom)
        self.assertEqual(res_xpath["action"], "click_xpath")
        self.assertEqual(len(web.history), 6)

    def test_embedding_search_prefers_closest(self):
        """Ensure embedding search sorts by cosine similarity."""
        node_close = Node(kind="Concept", labels=["a"], props={"name": "A"}, llm_embedding=[1, 0])
        node_far = Node(kind="Concept", labels=["b"], props={"name": "B"}, llm_embedding=[0, 1])
        self.memory.upsert(node_close, self.provenance)
        self.memory.upsert(node_far, self.provenance)

        results = self.memory.search("query", top_k=1, query_embedding=[1, 0])
        self.assertEqual(results[0]["uuid"], node_close.uuid)

if __name__ == '__main__':
    unittest.main()
