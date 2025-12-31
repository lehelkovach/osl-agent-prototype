import subprocess
from typing import Dict, Any

from src.personal_assistant.tools import ShellTools


class RealShellTools(ShellTools):
    """Runs shell commands with staging support."""

    def run(self, command: str, dry_run: bool = True) -> Dict[str, Any]:
        if dry_run:
            return {"status": "staged", "command": command, "dry_run": True}
        try:
            completed = subprocess.run(
                command,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
            )
            return {
                "status": "executed",
                "command": command,
                "dry_run": False,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        except Exception as exc:  # pragma: no cover - defensive
            return {"status": "error", "command": command, "error": str(exc)}
