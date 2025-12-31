import unittest

from src.personal_assistant.local_embedder import LocalEmbedder


class TestLocalEmbedder(unittest.TestCase):
    def test_hash_fallback(self):
        emb = LocalEmbedder(dim=8)
        vec = emb.embed("hello")
        self.assertEqual(len(vec), 8)
        self.assertTrue(all(isinstance(x, float) for x in vec))


if __name__ == "__main__":
    unittest.main()
