#!/usr/bin/env python3
import argparse
import json
import os
import time
import urllib.request
from typing import Any, Dict


DEFAULT_ENV = {
    "HOST": "127.0.0.1",
    "PORT": "8000",
    "SURVEY_URL": "https://example.com/survey",
    "CONTINUE_SELECTOR": "button:has-text(\"Continue\")",
    "FINISH_SELECTOR": "button:has-text(\"Finish\")",
}


def _load_yaml(path: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    if yaml:
        return yaml.safe_load(raw)

    # YAML 1.2 is a superset of JSON; allow JSON-formatted YAML files.
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "PyYAML is not installed and file is not JSON-compatible YAML. "
            "Install PyYAML or use JSON-formatted YAML."
        ) from exc


def _expand_env(obj: Any) -> Any:
    if isinstance(obj, str):
        text = obj
        for key, default in DEFAULT_ENV.items():
            if f"${{{key}}}" in text and not os.getenv(key):
                text = text.replace(f"${{{key}}}", default)
        return os.path.expandvars(text)
    if isinstance(obj, list):
        return [_expand_env(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    return obj


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}


def run_flow(config: Dict[str, Any], dry_run: bool = False) -> int:
    config = _expand_env(config)
    base_url = config.get("base_url") or "http://127.0.0.1:8000"
    endpoint = config.get("endpoint") or "/chat"
    if "${" in base_url or base_url == "http://:":
        base_url = "http://127.0.0.1:8000"
    steps = config.get("steps") or []
    if not steps:
        raise RuntimeError("No steps defined in YAML")

    failures = 0
    for idx, step in enumerate(steps, start=1):
        name = step.get("name") or f"step_{idx}"
        if step.get("pause_ms"):
            wait_s = float(step["pause_ms"]) / 1000.0
            print(f"[{idx}] {name}: pause {wait_s:.2f}s")
            time.sleep(wait_s)
            continue

        message = step.get("message")
        if not message:
            raise RuntimeError(f"Step {idx} missing message")

        payload = {"message": message}
        if step.get("feedback"):
            payload["feedback"] = step["feedback"]
        if step.get("trace_id"):
            payload["trace_id"] = step["trace_id"]

        print(f"[{idx}] {name}: sending message")
        if dry_run:
            print(json.dumps(payload, indent=2))
            continue

        response = _post_json(base_url + endpoint, payload)
        print(json.dumps(response, indent=2)[:2000])

        expect_status = step.get("expect_status")
        if expect_status:
            status = (
                response.get("execution_results", {})
                .get("status")
            )
            if status != expect_status:
                failures += 1
                print(f"[warn] expected status {expect_status}, got {status}")

        expect_contains = step.get("expect_contains") or []
        if isinstance(expect_contains, str):
            expect_contains = [expect_contains]
        if expect_contains:
            raw = json.dumps(response)
            for needle in expect_contains:
                if needle not in raw:
                    failures += 1
                    print(f"[warn] missing expected token: {needle}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live debug flow from YAML")
    parser.add_argument("--config", default="scripts/live_survey_flow.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = _load_yaml(args.config)
    failures = run_flow(config, dry_run=args.dry_run)
    if failures:
        print(f"Completed with {failures} warnings")
        return 1
    print("Completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
