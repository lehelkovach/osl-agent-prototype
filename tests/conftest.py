"""
Pytest configuration that ensures the project root is importable so tests can
`import src.personal_assistant.*` regardless of how pytest is invoked.
"""
import os
import socket
import sys
from urllib.parse import urlparse

import pytest
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_arango_status = None
_openai_status = None


def _load_env():
    load_dotenv(".env.local")
    load_dotenv()


def _is_placeholder(val: str) -> bool:
    """
    Treat redacted placeholder values (used in cloud workspaces) as unset.
    """
    if not val:
        return False
    lowered = val.strip().lower()
    return "__redact" in lowered or lowered.startswith("redacted")


def _resolve_verify(env_val: str):
    if not env_val:
        return True
    lowered = env_val.lower()
    if lowered in ("false", "0", "no"):
        return False
    if lowered in ("true", "1", "yes"):
        return True
    return os.path.abspath(os.path.expanduser(env_val))


def _compute_arango_status():
    global _arango_status
    if _arango_status is not None:
        return _arango_status

    _load_env()
    required = [os.getenv("ARANGO_URL"), os.getenv("ARANGO_USER"), os.getenv("ARANGO_PASSWORD")]
    if not all(required) or any(_is_placeholder(v or "") for v in required):
        _arango_status = {"state": "skip", "reason": "Arango env not set"}
        return _arango_status

    try:
        from arango import ArangoClient  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - optional dependency
        _arango_status = {"state": "skip", "reason": f"Arango driver missing: {exc}"}
        return _arango_status

    parsed = urlparse(os.getenv("ARANGO_URL", ""))
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if host:
        try:
            with socket.create_connection((host, port), timeout=5):
                pass
        except OSError as exc:
            _arango_status = {"state": "fail", "reason": f"Cannot reach Arango at {host}:{port}: {exc}"}
            return _arango_status

    verify_env = os.getenv("ARANGO_VERIFY")
    verify = _resolve_verify(verify_env)
    if isinstance(verify, str) and not os.path.exists(verify):
        _arango_status = {"state": "fail", "reason": f"ARANGO_VERIFY path not found: {verify}"}
        return _arango_status
    try:
        client = ArangoClient(hosts=os.environ["ARANGO_URL"], verify_override=verify)
        sys_db = client.db(
            "_system",
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASSWORD"],
        )
        target_db = os.getenv("ARANGO_DB", "agent_memory")
        if not sys_db.has_database(target_db):
            _arango_status = {"state": "fail", "reason": f"Expected DB '{target_db}' to exist"}
            return _arango_status
    except Exception as exc:  # pragma: no cover - network path
        detail = f"Arango connection failed: {exc}"
        if verify_env:
            detail += f" (verify={verify_env})"
        _arango_status = {"state": "fail", "reason": detail}
        return _arango_status

    _arango_status = {"state": "ok", "client": client, "sys_db": sys_db, "target_db": target_db}
    return _arango_status


def _compute_openai_status():
    global _openai_status
    if _openai_status is not None:
        return _openai_status

    _load_env()
    if os.getenv("USE_FAKE_OPENAI") == "1":
        _openai_status = {"state": "skip", "reason": "USE_FAKE_OPENAI=1"}
        return _openai_status
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or _is_placeholder(api_key):
        _openai_status = {"state": "skip", "reason": "OPENAI_API_KEY not set"}
        return _openai_status

    try:
        from openai import OpenAI  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - optional dependency
        _openai_status = {"state": "fail", "reason": f"OpenAI SDK missing: {exc}"}
        return _openai_status

    chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
    embed_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    try:
        client = OpenAI(api_key=api_key)
        models = {m.id for m in client.models.list().data}
        if chat_model not in models:
            _openai_status = {"state": "fail", "reason": f"Chat model '{chat_model}' not available"}
            return _openai_status
        if embed_model not in models:
            _openai_status = {"state": "fail", "reason": f"Embedding model '{embed_model}' not available"}
            return _openai_status
    except Exception as exc:  # pragma: no cover - network path
        _openai_status = {"state": "fail", "reason": f"OpenAI check failed: {exc}"}
        return _openai_status

    _openai_status = {"state": "ok", "client": client, "models": models}
    return _openai_status


@pytest.fixture(scope="session")
def arango_status():
    return _compute_arango_status()


@pytest.fixture(scope="session")
def require_arango_connection(arango_status):
    if arango_status["state"] == "skip":
        pytest.skip(arango_status["reason"])
    if arango_status["state"] == "fail":
        pytest.skip(arango_status["reason"])
    return arango_status


@pytest.fixture(scope="session")
def openai_status():
    return _compute_openai_status()


@pytest.fixture(scope="session")
def require_openai_service(openai_status):
    if openai_status["state"] == "skip":
        pytest.skip(openai_status["reason"])
    if openai_status["state"] == "fail":
        pytest.skip(openai_status["reason"])
    return openai_status


def pytest_collection_modifyitems(session, config, items):
    def sort_key(item):
        path = str(item.fspath)
        if path.endswith("test_arango_connection.py"):
            return (0, path, item.name)
        if path.endswith("test_arango_aql_queries.py"):
            return (1, path, item.name)
        return (2, path, item.name)

    items.sort(key=sort_key)
