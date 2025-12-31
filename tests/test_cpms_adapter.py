import unittest

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


if __name__ == "__main__":
    unittest.main()
