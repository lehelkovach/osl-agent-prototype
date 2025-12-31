import pytest
import importlib


def pytest_report_header(config):
    infos = []
    # Playwright availability
    try:
        importlib.import_module("playwright")
        infos.append("Playwright: available")
    except Exception:
        infos.append("Playwright: NOT available (web UI tests may be mocked)")
    # Arango env
    import os
    arango_ready = all(os.getenv(k) for k in ["ARANGO_URL", "ARANGO_USER", "ARANGO_PASSWORD"])
    infos.append(f"Arango env: {'set' if arango_ready else 'missing (Arango tests mocked)'}")
    # CPMS env
    cpms_ready = bool(os.getenv("CPMS_BASE_URL")) and bool(os.getenv("CPMS_TOKEN") or os.getenv("CPMS_API_KEY"))
    infos.append(f"CPMS env: {'set' if cpms_ready else 'missing (CPMS uses fake)'}")
    return " | ".join(infos)
