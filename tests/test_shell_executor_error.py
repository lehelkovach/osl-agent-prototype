import unittest

from src.personal_assistant.shell_executor import RealShellTools


class TestShellExecutorError(unittest.TestCase):
    def test_execute_nonzero(self):
        shell = RealShellTools()
        res = shell.run("exit 1", dry_run=False)
        self.assertEqual(res["status"], "executed")
        self.assertNotEqual(res["returncode"], 0)
        self.assertTrue("returncode" in res)


if __name__ == "__main__":
    unittest.main()
