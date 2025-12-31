import subprocess
import sys
import os
import unittest


class TestRunScriptSmoke(unittest.TestCase):
    def test_run_agent_ui_script_imports(self):
        script = os.path.join(os.path.dirname(__file__), "..", "scripts", "run_agent_ui.sh")
        env = os.environ.copy()
        env["RUN_AGENT_TEST"] = "1"
        proc = subprocess.run(
            ["bash", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout)
        self.assertIn("import_ok", proc.stdout)


if __name__ == "__main__":
    unittest.main()
