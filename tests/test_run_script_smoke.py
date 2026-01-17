import subprocess
import sys
import os
import unittest
import pytest


class TestRunScriptSmoke(unittest.TestCase):
    @pytest.mark.skipif(sys.platform == "win32", reason="Bash scripts not available on Windows")
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
