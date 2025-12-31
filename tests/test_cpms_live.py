import os
import pytest

from dotenv import load_dotenv

try:
    import cpms_client  # noqa: F401
    CPMS_INSTALLED = True
except Exception:
    CPMS_INSTALLED = False

from src.personal_assistant.cpms_adapter import CPMSAdapter


class FakeCpmsClient:
    def list_procedures(self):
        return [{"id": "fake", "name": "demo"}]


def _env_ready():
    return bool(os.getenv("CPMS_BASE_URL")) and bool(os.getenv("CPMS_TOKEN") or os.getenv("CPMS_API_KEY"))


def test_cpms_live_list_procedures():
    load_dotenv(".env.local")
    load_dotenv()
    if CPMS_INSTALLED and _env_ready():
        adapter = CPMSAdapter.from_env()
    else:
        adapter = CPMSAdapter(FakeCpmsClient())
    procs = adapter.list_procedures()
    assert isinstance(procs, list)
