import os
import tempfile
import unittest
import logging

from src.personal_assistant.logging_setup import configure_logging, get_logger


class TestLoggingFile(unittest.TestCase):
    def test_logs_written_to_file(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        os.environ["AGENT_LOG_FILE"] = path
        configure_logging()
        log = get_logger("test")
        log.info("file_log_test", key="val")
        # Flush stdlib handlers
        for h in logging.getLogger().handlers:
            h.flush()
        with open(path, "r") as f:
            data = f.read()
        self.assertIn("file_log_test", data)
        os.remove(path)
        os.environ.pop("AGENT_LOG_FILE", None)


if __name__ == "__main__":
    unittest.main()
