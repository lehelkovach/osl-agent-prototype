import os
from unittest import mock

from src.personal_assistant import service
from src.personal_assistant.openai_client import FakeOpenAIClient


def test_load_config_overrides(tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text("port: 1234\nembedding_backend: local\n")
    cfg = service.load_config(str(custom))
    # Default keys from default.yaml are present, override applied
    assert cfg["port"] == 1234
    assert cfg["embedding_backend"] == "local"
    default_cfg = service.load_config(None)
    assert "host" in default_cfg


def test_default_agent_respects_config_flags(monkeypatch):
    cfg = {
        "embedding_backend": "local",
        "use_fake_openai": True,
        "use_cpms_for_procs": False,
        "arango": {"url": ""},
        "chroma": {"path": ".chroma-test"},
    }
    with mock.patch.dict(os.environ, {}, clear=True):
        agent = service.default_agent_from_env(cfg)
    # Fake client should be selected from config flag
    assert isinstance(agent.openai_client, FakeOpenAIClient)
    # Memory should be initialized (Chroma fallback or mock)
    assert agent.memory is not None
