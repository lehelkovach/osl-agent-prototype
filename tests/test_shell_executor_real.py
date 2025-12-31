import unittest

from src.personal_assistant.shell_executor import RealShellTools


class TestRealShellTools(unittest.TestCase):
    def test_dry_run(self):
        shell = RealShellTools()
        res = shell.run("echo hello", dry_run=True)
        self.assertEqual(res["status"], "staged")
        self.assertTrue(res["dry_run"])

    def test_execute_echo(self):
        shell = RealShellTools()
        res = shell.run("echo 42", dry_run=False)
        self.assertEqual(res["status"], "executed")
        self.assertEqual(res["returncode"], 0)
        self.assertIn("42", res["stdout"])


if __name__ == "__main__":
    unittest.main()
