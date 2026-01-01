import unittest

import pytest

try:
    import sentence_transformers  # noqa: F401
    SENT_AVAILABLE = True
except Exception:
    SENT_AVAILABLE = False

from src.personal_assistant.local_embedder import LocalEmbedder


@pytest.mark.skipif(not SENT_AVAILABLE, reason="sentence-transformers not installed")
class TestLocalEmbedderModel(unittest.TestCase):
    def test_model_embedding(self):
        emb = LocalEmbedder()
        vec = emb.embed("hello world")
        self.assertGreater(len(vec), 10)


if __name__ == "__main__":
    unittest.main()
