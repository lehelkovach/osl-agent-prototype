"""
Thin adapter around `cpms-client` so the agent can create/list procedures/tasks in CPMS.

The adapter is dependency-injected to avoid hard failures when `cpms-client` is absent.
Use CPMSAdapter.from_env() if you want to build a real client from environment variables.
"""
from typing import Any, Dict, List, Optional
import os


class CPMSNotInstalled(RuntimeError):
    pass


class CPMSAdapter:
    def __init__(self, client: Any):
        """
        client is expected to expose:
          - create_procedure(name: str, description: str, steps: list[dict]) -> dict
          - list_procedures() -> list[dict]
          - get_procedure(procedure_id: str) -> dict
          - create_task(procedure_id: str, title: str, payload: dict) -> dict (optional)
          - list_tasks(procedure_id: Optional[str]) -> list[dict] (optional)
        """
        self.client = client

    @classmethod
    def from_env(cls):
        """
        Instantiate using cpms-client if installed. Expects:
        - CPMS_BASE_URL
        - CPMS_TOKEN (or CPMS_API_KEY)
        """
        try:
            from cpms_client import Client  # type: ignore
        except Exception as exc:  # pragma: no cover - exercised only when dependency missing
            raise CPMSNotInstalled("cpms-client is not installed; pip install cpms-client") from exc
        base_url = os.getenv("CPMS_BASE_URL", "http://localhost:3000")
        token = os.getenv("CPMS_TOKEN") or os.getenv("CPMS_API_KEY")
        client = Client(base_url=base_url, token=token)  # type: ignore[arg-type]
        return cls(client)

    def create_procedure(self, name: str, description: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.client.create_procedure(name=name, description=description, steps=steps)

    def list_procedures(self) -> List[Dict[str, Any]]:
        return self.client.list_procedures()

    def get_procedure(self, procedure_id: str) -> Dict[str, Any]:
        return self.client.get_procedure(procedure_id)

    def create_task(self, procedure_id: str, title: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not hasattr(self.client, "create_task"):
            raise NotImplementedError("Underlying CPMS client does not support create_task")
        return self.client.create_task(procedure_id=procedure_id, title=title, payload=payload)

    def list_tasks(self, procedure_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not hasattr(self.client, "list_tasks"):
            raise NotImplementedError("Underlying CPMS client does not support list_tasks")
        if procedure_id:
            return self.client.list_tasks(procedure_id=procedure_id)
        return self.client.list_tasks()
