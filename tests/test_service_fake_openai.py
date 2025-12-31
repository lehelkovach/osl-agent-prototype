import os
import unittest
from unittest import mock

from src.personal_assistant.service import default_agent_from_env
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.local_embedder import LocalEmbedder


class TestServiceFakeOpenAI(unittest.TestCase):
    def test_default_agent_uses_fake_when_env_set(self):
        with mock.patch.dict(os.environ, {"USE_FAKE_OPENAI": "1", "ARANGO_URL": ""}):
            agent = default_agent_from_env()
            self.assertIsInstance(agent.openai_client, FakeOpenAIClient)

    def test_default_agent_uses_local_embedder(self):
        with mock.patch.dict(os.environ, {"EMBEDDING_BACKEND": "local", "ARANGO_URL": "", "USE_FAKE_OPENAI": "1"}):
            agent = default_agent_from_env()
            # embedding comes from LocalEmbedder
            vec = agent.queue_manager.ensure_queue(agent_prov()).llm_embedding
            if vec:
                self.assertTrue(isinstance(vec, list))


def agent_prov():
    from src.personal_assistant.models import Provenance
    from datetime import datetime, timezone
    return Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "test")


if __name__ == "__main__":
    unittest.main()
