import os
import tempfile
import unittest
import logging

from src.personal_assistant.logging_setup import configure_logging, get_logger


class TestLoggingFile(unittest.TestCase):
    def test_logs_written_to_file(self):
        import sys
        import time
        
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            os.environ["AGENT_LOG_FILE"] = path
            configure_logging()
            log = get_logger("test")
            log.info("file_log_test", key="val")
            # Flush stdlib handlers
            for h in logging.getLogger().handlers:
                h.flush()
                # Close file handlers to release file locks (Windows compatibility)
                if hasattr(h, 'close'):
                    try:
                        h.close()
                    except Exception:
                        pass
            # Small delay for Windows file system
            if sys.platform == "win32":
                time.sleep(0.1)
            with open(path, "r") as f:
                data = f.read()
            self.assertIn("file_log_test", data)
        finally:
            # Cleanup with retry for Windows file locking
            import shutil
            for _ in range(3):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                    break
                except (PermissionError, OSError):
                    time.sleep(0.1)
            os.environ.pop("AGENT_LOG_FILE", None)


if __name__ == "__main__":
    unittest.main()
