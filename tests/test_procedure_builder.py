import unittest

from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.procedure_builder import ProcedureBuilder


class TestProcedureBuilder(unittest.TestCase):
    def test_create_procedure_with_dependencies_and_guards(self):
        memory = MockMemoryTools()
        builder = ProcedureBuilder(memory, embed_fn=lambda text: [float(len(text)), 0.1])
        steps = [
            {"title": "Open LinkedIn", "payload": {"url": "https://linkedin.com"}},
            {"title": "Open messages", "payload": {"url": "https://linkedin.com/messages"}},
            {"title": "Create reminder task", "payload": {"action": "tasks.create"}},
        ]
        deps = [(0, 1), (1, 2)]  # step1 depends on 0, step2 depends on 1
        guards = {2: "only if new recruiter messages"}

        res = builder.create_procedure(
            title="Check LinkedIn messages",
            description="Open LinkedIn and create reminders for recruiter messages",
            steps=steps,
            dependencies=deps,
            guards=guards,
            extra_props={"tested": True},
        )

        proc_uuid = res["procedure_uuid"]
        step_uuids = res["step_uuids"]
        self.assertEqual(len(step_uuids), 3)

        proc_nodes = [n for n in memory.nodes.values() if n.kind == "Procedure"]
        self.assertEqual(len(proc_nodes), 1)
        self.assertEqual(proc_nodes[0].uuid, proc_uuid)
        self.assertIsNotNone(proc_nodes[0].llm_embedding)

        step_nodes = [n for n in memory.nodes.values() if n.kind == "Step"]
        self.assertEqual(len(step_nodes), 3)
        for n in step_nodes:
            self.assertIsNotNone(n.llm_embedding)
        # Guard applied to the third step
        guarded = [n for n in step_nodes if n.props.get("guard_text")]
        self.assertEqual(len(guarded), 1)
        self.assertEqual(guarded[0].props["guard_text"], "only if new recruiter messages")

        # Dependency edges
        dep_edges = [e for e in memory.edges.values() if e.rel == "depends_on"]
        self.assertEqual(len(dep_edges), 2)

    def test_cycle_detection(self):
        memory = MockMemoryTools()
        builder = ProcedureBuilder(memory, embed_fn=lambda text: [1.0, 0.0])
        steps = [{"title": "A"}, {"title": "B"}]
        deps = [(0, 1), (1, 0)]  # cycle
        with self.assertRaises(ValueError):
            builder.create_procedure(
                title="Cyclic",
                description="cycle",
                steps=steps,
                dependencies=deps,
            )

    def test_search_procedure(self):
        memory = MockMemoryTools()
        builder = ProcedureBuilder(memory, embed_fn=lambda text: [float(len(text)), 0.1])
        builder.create_procedure(
            title="LinkedIn recruiter follow-up",
            description="Check recruiter messages",
            steps=[{"title": "Open LinkedIn"}],
        )
        results = builder.search_procedures("LinkedIn recruiter")
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("LinkedIn", results[0].get("props", {}).get("title", ""))


if __name__ == "__main__":
    unittest.main()
