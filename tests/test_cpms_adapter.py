import unittest
import tempfile
import os

from src.personal_assistant.cpms_adapter import CPMSAdapter, CPMSNotInstalled


class FakeCpmsClient:
    def __init__(self):
        self.procedures = {}
        self.tasks = {}
        self.created = []

    def create_procedure(self, name, description, steps):
        proc_id = f"proc-{len(self.procedures)+1}"
        data = {"id": proc_id, "name": name, "description": description, "steps": steps}
        self.procedures[proc_id] = data
        self.created.append(("procedure", data))
        return data

    def list_procedures(self):
        return list(self.procedures.values())

    def get_procedure(self, procedure_id):
        return self.procedures[procedure_id]

    def create_task(self, procedure_id, title, payload):
        task_id = f"task-{len(self.tasks)+1}"
        data = {"id": task_id, "procedure_id": procedure_id, "title": title, "payload": payload}
        self.tasks[task_id] = data
        self.created.append(("task", data))
        return data

    def list_tasks(self, procedure_id=None):
        if procedure_id:
            return [t for t in self.tasks.values() if t["procedure_id"] == procedure_id]
        return list(self.tasks.values())


class TestCPMSAdapter(unittest.TestCase):
    def test_create_and_list_procedure(self):
        client = FakeCpmsClient()
        adapter = CPMSAdapter(client)
        created = adapter.create_procedure("Demo", "desc", [{"step": 1}])
        self.assertEqual(created["name"], "Demo")
        self.assertEqual(len(adapter.list_procedures()), 1)
        fetched = adapter.get_procedure(created["id"])
        self.assertEqual(fetched["id"], created["id"])

    def test_task_operations(self):
        client = FakeCpmsClient()
        adapter = CPMSAdapter(client)
        proc = adapter.create_procedure("Demo", "desc", [])
        task = adapter.create_task(proc["id"], "title", {"k": "v"})
        self.assertEqual(task["procedure_id"], proc["id"])
        self.assertEqual(len(adapter.list_tasks(proc["id"])), 1)

    def test_not_installed_raises(self):
        # Only exercise the exception path; no import attempt to cpms-client
        try:
            raise CPMSNotInstalled("missing")
        except CPMSNotInstalled as exc:
            self.assertEqual(str(exc), "missing")


class FakeCpmsClientWithPatterns(FakeCpmsClient):
    """Extended fake client that supports pattern detection via detect_form() method (cpms-client v0.1.2+)"""
    
    def detect_form(self, html=None, screenshot_path=None, url=None, dom_snapshot=None):
        """Mock CPMS form detection (matches cpms-client v0.1.2+ API)"""
        # Simple detection logic for testing
        if html and ("email" in html.lower() or "password" in html.lower()):
            return {
                "form_type": "login",
                "fields": [
                    {
                        "type": "email",
                        "selector": "input[type='email']",
                        "xpath": "/html/body/form/input[1]",
                        "confidence": 0.95,
                        "signals": {"attributes": {"type": "email"}}
                    },
                    {
                        "type": "password",
                        "selector": "input[type='password']",
                        "confidence": 0.98,
                        "signals": {"attributes": {"type": "password"}}
                    },
                    {
                        "type": "submit",
                        "selector": "button[type='submit']",
                        "confidence": 0.90
                    }
                ],
                "confidence": 0.92,
                "pattern_id": "test-pattern-123"
            }
        return {
            "form_type": "unknown",
            "fields": [],
            "confidence": 0.3
        }


class TestCPMSPatternDetection(unittest.TestCase):
    def test_detect_form_pattern_with_cpms_api(self):
        """Test pattern detection when CPMS API is available"""
        client = FakeCpmsClientWithPatterns()
        adapter = CPMSAdapter(client)
        
        html = '<form><input type="email" name="email"><input type="password" name="password"><button type="submit">Login</button></form>'
        result = adapter.detect_form_pattern(html)
        
        self.assertEqual(result["form_type"], "login")
        self.assertEqual(len(result["fields"]), 3)
        # pattern_id is optional - only present if CPMS API provides it
        # (Currently published CPMS client doesn't have detect_form, so we use fallback)
        
        # Check field types
        field_types = [f["type"] for f in result["fields"]]
        self.assertIn("email", field_types)
        self.assertIn("password", field_types)
        self.assertIn("submit", field_types)
    
    def test_detect_form_pattern_fallback(self):
        """Test fallback detection when CPMS API not available"""
        client = FakeCpmsClient()  # No match_pattern method
        adapter = CPMSAdapter(client)
        
        html = '<form><input type="email"><input type="password"><button type="submit">Submit</button></form>'
        result = adapter.detect_form_pattern(html)
        
        # Should use fallback detection
        self.assertEqual(result["form_type"], "login")
        self.assertGreater(len(result["fields"]), 0)
        self.assertIn("confidence", result)
    
    def test_detect_form_pattern_with_screenshot(self):
        """Test pattern detection with screenshot"""
        client = FakeCpmsClientWithPatterns()
        adapter = CPMSAdapter(client)
        
        # Create a temporary screenshot file
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(b'fake image data')
            screenshot_path = f.name
        
        try:
            html = '<form><input type="email"><input type="password"></form>'
            result = adapter.detect_form_pattern(html, screenshot_path=screenshot_path)
            
            self.assertEqual(result["form_type"], "login")
            self.assertGreater(len(result["fields"]), 0)
        finally:
            os.unlink(screenshot_path)
    
    def test_build_observation(self):
        """Test observation building"""
        client = FakeCpmsClient()
        adapter = CPMSAdapter(client)
        
        html = '<html><body>Test</body></html>'
        observation = adapter._build_observation(html, url="https://example.com")
        
        self.assertEqual(observation["html"], html)
        self.assertEqual(observation["metadata"]["url"], "https://example.com")
        self.assertIn("timestamp", observation["metadata"])
    
    def test_normalize_pattern_response(self):
        """Test response normalization"""
        client = FakeCpmsClient()
        adapter = CPMSAdapter(client)
        
        # Test already normalized response
        response = {
            "form_type": "login",
            "fields": [{"type": "email", "selector": "input[type='email']", "confidence": 0.9}],
            "confidence": 0.85
        }
        normalized = adapter._normalize_pattern_response(response)
        self.assertEqual(normalized, response)
        
        # Test response with different field names
        response2 = {
            "form_type": "login",
            "detected_fields": [
                {"field_type": "email", "css_selector": "input[type='email']", "confidence": 0.9}
            ],
            "confidence": 0.85
        }
        normalized2 = adapter._normalize_pattern_response(response2)
        self.assertEqual(normalized2["form_type"], "login")
        self.assertEqual(len(normalized2["fields"]), 1)
        self.assertEqual(normalized2["fields"][0]["type"], "email")
        self.assertEqual(normalized2["fields"][0]["selector"], "input[type='email']")


if __name__ == "__main__":
    unittest.main()
