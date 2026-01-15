"""
Safe Shell Executor - Sandboxed command execution with rollback support.

Provides safety features for running shell commands:
- Command whitelist/blacklist filtering
- Temporary directory sandboxing
- File change tracking and rollback
- Timeout and resource limits
- Dry-run preview mode
"""
import os
import re
import shutil
import subprocess
import tempfile
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager

from src.personal_assistant.tools import ShellTools

logger = logging.getLogger(__name__)


@dataclass
class FileSnapshot:
    """Snapshot of a file for rollback."""
    path: str
    existed: bool
    content: Optional[bytes] = None
    mode: Optional[int] = None
    hash: Optional[str] = None


@dataclass
class CommandResult:
    """Result of a command execution."""
    command: str
    status: str  # "success", "error", "blocked", "staged", "rolled_back"
    returncode: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    dry_run: bool = False
    sandbox: bool = False
    execution_time_ms: int = 0
    files_modified: List[str] = field(default_factory=list)
    rollback_available: bool = False


class CommandPolicy:
    """Policy for command filtering and safety."""
    
    # Commands that are always blocked (dangerous operations)
    BLOCKED_COMMANDS = {
        "rm -rf /",
        "rm -rf /*",
        "mkfs",
        "dd if=/dev/zero",
        ":(){ :|:& };:",  # fork bomb
        "> /dev/sda",
        "chmod -R 777 /",
        "chown -R",
    }
    
    # Patterns for dangerous commands
    BLOCKED_PATTERNS = [
        r"rm\s+-rf\s+/[^/]",  # rm -rf on root-level dirs
        r">\s*/dev/",  # redirect to devices
        r"mkfs\.",  # format filesystems
        r"dd\s+if=.*/dev/",  # dd from devices
        r"curl.*\|\s*(ba)?sh",  # curl pipe to shell
        r"wget.*\|\s*(ba)?sh",  # wget pipe to shell
        r"chmod\s+-R\s+777\s+/",  # chmod 777 on root
        r"sudo\s+rm",  # sudo rm
        r"sudo\s+dd",  # sudo dd
    ]
    
    # Safe commands that don't need sandbox
    SAFE_COMMANDS = {
        "ls", "pwd", "whoami", "date", "echo", "cat", "head", "tail",
        "grep", "find", "which", "type", "env", "printenv",
        "python --version", "pip --version", "node --version",
        "git status", "git log", "git diff", "git branch",
    }
    
    # Commands that modify files (need tracking)
    FILE_MODIFYING_PATTERNS = [
        r"(^|\s)(cp|mv|rm|mkdir|rmdir|touch|chmod|chown)\s",
        r">\s*\S",  # redirect to file
        r">>\s*\S",  # append to file
        r"(^|\s)(sed|awk)\s+-i",  # in-place editing
        r"(^|\s)tee\s",
        r"(^|\s)(pip|npm|yarn|poetry)\s+(install|uninstall)",
    ]
    
    def __init__(
        self,
        additional_blocked: Optional[Set[str]] = None,
        additional_safe: Optional[Set[str]] = None,
        allow_sudo: bool = False,
        allow_network: bool = True,
    ):
        self.blocked_commands = self.BLOCKED_COMMANDS.copy()
        self.safe_commands = self.SAFE_COMMANDS.copy()
        
        if additional_blocked:
            self.blocked_commands.update(additional_blocked)
        if additional_safe:
            self.safe_commands.update(additional_safe)
        
        self.allow_sudo = allow_sudo
        self.allow_network = allow_network
    
    def is_blocked(self, command: str) -> tuple[bool, Optional[str]]:
        """Check if command is blocked. Returns (blocked, reason)."""
        cmd_lower = command.lower().strip()
        
        # Check exact matches
        for blocked in self.blocked_commands:
            if blocked.lower() in cmd_lower:
                return True, f"Blocked command pattern: {blocked}"
        
        # Check patterns
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, cmd_lower):
                return True, f"Matches blocked pattern: {pattern}"
        
        # Check sudo
        if not self.allow_sudo and re.search(r"(^|\s)sudo\s", cmd_lower):
            return True, "sudo not allowed"
        
        # Check network commands if disabled
        if not self.allow_network:
            network_cmds = ["curl", "wget", "ssh", "scp", "rsync", "nc", "netcat"]
            for nc in network_cmds:
                if re.search(rf"(^|\s){nc}\s", cmd_lower):
                    return True, f"Network command not allowed: {nc}"
        
        return False, None
    
    def is_safe(self, command: str) -> bool:
        """Check if command is in safe list (no sandbox needed)."""
        cmd_stripped = command.strip()
        
        # Check exact matches
        if cmd_stripped in self.safe_commands:
            return True
        
        # Check if starts with safe command
        for safe in self.safe_commands:
            if cmd_stripped.startswith(safe):
                return True
        
        return False
    
    def modifies_files(self, command: str) -> bool:
        """Check if command might modify files."""
        for pattern in self.FILE_MODIFYING_PATTERNS:
            if re.search(pattern, command):
                return True
        return False


class FileTracker:
    """Tracks file changes for rollback support."""
    
    def __init__(self, track_dirs: Optional[List[str]] = None):
        self.snapshots: Dict[str, FileSnapshot] = {}
        self.track_dirs = track_dirs or [os.getcwd()]
    
    def snapshot_file(self, path: str) -> FileSnapshot:
        """Take a snapshot of a file."""
        abs_path = os.path.abspath(path)
        
        if os.path.exists(abs_path):
            with open(abs_path, "rb") as f:
                content = f.read()
            snapshot = FileSnapshot(
                path=abs_path,
                existed=True,
                content=content,
                mode=os.stat(abs_path).st_mode,
                hash=hashlib.sha256(content).hexdigest()
            )
        else:
            snapshot = FileSnapshot(
                path=abs_path,
                existed=False
            )
        
        self.snapshots[abs_path] = snapshot
        return snapshot
    
    def snapshot_directory(self, directory: str) -> List[FileSnapshot]:
        """Snapshot all files in a directory."""
        snapshots = []
        dir_path = Path(directory)
        
        if dir_path.exists():
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    snapshots.append(self.snapshot_file(str(file_path)))
        
        return snapshots
    
    def get_modified_files(self) -> List[str]:
        """Get list of files that have been modified since snapshot."""
        modified = []
        
        for path, snapshot in self.snapshots.items():
            if snapshot.existed:
                if not os.path.exists(path):
                    modified.append(path)  # Deleted
                else:
                    with open(path, "rb") as f:
                        current_hash = hashlib.sha256(f.read()).hexdigest()
                    if current_hash != snapshot.hash:
                        modified.append(path)  # Modified
            else:
                if os.path.exists(path):
                    modified.append(path)  # Created
        
        return modified
    
    def rollback(self) -> List[str]:
        """Rollback all tracked files to their snapshot state."""
        rolled_back = []
        
        for path, snapshot in self.snapshots.items():
            try:
                if snapshot.existed:
                    # Restore original content
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(snapshot.content)
                    if snapshot.mode:
                        os.chmod(path, snapshot.mode)
                    rolled_back.append(path)
                else:
                    # File didn't exist, delete if it was created
                    if os.path.exists(path):
                        os.remove(path)
                        rolled_back.append(path)
            except Exception as e:
                logger.error(f"Failed to rollback {path}: {e}")
        
        return rolled_back
    
    def clear(self):
        """Clear all snapshots."""
        self.snapshots.clear()


class SafeShellExecutor(ShellTools):
    """
    Safe shell executor with sandbox and rollback capabilities.
    
    Features:
    - Command filtering (whitelist/blacklist)
    - Temporary directory sandboxing
    - File change tracking and rollback
    - Timeout limits
    - Dry-run preview mode
    """
    
    def __init__(
        self,
        policy: Optional[CommandPolicy] = None,
        sandbox_dir: Optional[str] = None,
        timeout_seconds: int = 30,
        track_files: bool = True,
        working_dir: Optional[str] = None,
    ):
        self.policy = policy or CommandPolicy()
        self.sandbox_dir = sandbox_dir
        self.timeout_seconds = timeout_seconds
        self.track_files = track_files
        self.working_dir = working_dir or os.getcwd()
        self.file_tracker = FileTracker() if track_files else None
        self._temp_sandbox: Optional[str] = None
    
    @contextmanager
    def sandbox_context(self):
        """Context manager for temporary sandbox directory."""
        if self.sandbox_dir:
            yield self.sandbox_dir
        else:
            temp_dir = tempfile.mkdtemp(prefix="safe_shell_")
            try:
                yield temp_dir
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def run(self, command: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        Run a shell command with safety checks.
        
        Args:
            command: The shell command to run
            dry_run: If True, only preview the command without executing
            
        Returns:
            Dict with execution result
        """
        start_time = datetime.now()
        
        # Check if blocked
        blocked, reason = self.policy.is_blocked(command)
        if blocked:
            return CommandResult(
                command=command,
                status="blocked",
                error=reason,
                dry_run=dry_run
            ).__dict__
        
        # Dry run mode - just preview
        if dry_run:
            is_safe = self.policy.is_safe(command)
            modifies = self.policy.modifies_files(command)
            
            return CommandResult(
                command=command,
                status="staged",
                dry_run=True,
                rollback_available=modifies and self.track_files,
            ).__dict__
        
        # Execute the command
        try:
            result = self._execute(command)
            result.execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return result.__dict__
        except Exception as e:
            return CommandResult(
                command=command,
                status="error",
                error=str(e),
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            ).__dict__
    
    def _execute(self, command: str) -> CommandResult:
        """Execute command with optional sandboxing."""
        use_sandbox = not self.policy.is_safe(command)
        
        # Track files if command modifies them
        if self.track_files and self.policy.modifies_files(command):
            # Snapshot current directory
            self.file_tracker.snapshot_directory(self.working_dir)
        
        if use_sandbox:
            return self._execute_sandboxed(command)
        else:
            return self._execute_direct(command)
    
    def _execute_direct(self, command: str) -> CommandResult:
        """Execute command directly."""
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            
            files_modified = []
            if self.file_tracker:
                files_modified = self.file_tracker.get_modified_files()
            
            return CommandResult(
                command=command,
                status="success" if completed.returncode == 0 else "error",
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                sandbox=False,
                files_modified=files_modified,
                rollback_available=bool(files_modified) and self.track_files,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                command=command,
                status="error",
                error=f"Command timed out after {self.timeout_seconds}s",
            )
    
    def _execute_sandboxed(self, command: str) -> CommandResult:
        """Execute command in sandbox environment."""
        with self.sandbox_context() as sandbox_dir:
            # Copy working directory to sandbox
            sandbox_work = os.path.join(sandbox_dir, "work")
            if os.path.exists(self.working_dir):
                shutil.copytree(
                    self.working_dir, 
                    sandbox_work,
                    ignore=shutil.ignore_patterns('.git', '__pycache__', 'node_modules', '.venv')
                )
            else:
                os.makedirs(sandbox_work)
            
            # Execute in sandbox
            env = os.environ.copy()
            env["HOME"] = sandbox_dir
            env["TMPDIR"] = sandbox_dir
            
            try:
                completed = subprocess.run(
                    command,
                    shell=True,
                    cwd=sandbox_work,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    env=env,
                )
                
                return CommandResult(
                    command=command,
                    status="success" if completed.returncode == 0 else "error",
                    returncode=completed.returncode,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    sandbox=True,
                    rollback_available=True,  # Sandbox auto-rolls back
                )
            except subprocess.TimeoutExpired:
                return CommandResult(
                    command=command,
                    status="error",
                    error=f"Command timed out after {self.timeout_seconds}s",
                    sandbox=True,
                )
    
    def run_in_sandbox(
        self,
        command: str,
        setup_commands: Optional[List[str]] = None,
        cleanup_commands: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run command in a fresh sandbox with optional setup/cleanup.
        
        Args:
            command: Main command to execute
            setup_commands: Commands to run before main command
            cleanup_commands: Commands to run after (even on failure)
            
        Returns:
            Combined results
        """
        results = {
            "setup_results": [],
            "main_result": None,
            "cleanup_results": [],
            "sandbox": True,
        }
        
        with self.sandbox_context() as sandbox_dir:
            sandbox_work = os.path.join(sandbox_dir, "work")
            os.makedirs(sandbox_work, exist_ok=True)
            
            env = os.environ.copy()
            env["HOME"] = sandbox_dir
            
            # Run setup commands
            if setup_commands:
                for setup_cmd in setup_commands:
                    try:
                        result = subprocess.run(
                            setup_cmd,
                            shell=True,
                            cwd=sandbox_work,
                            capture_output=True,
                            text=True,
                            timeout=self.timeout_seconds,
                            env=env,
                        )
                        results["setup_results"].append({
                            "command": setup_cmd,
                            "returncode": result.returncode,
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                        })
                    except Exception as e:
                        results["setup_results"].append({
                            "command": setup_cmd,
                            "error": str(e),
                        })
            
            # Run main command
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=sandbox_work,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    env=env,
                )
                results["main_result"] = {
                    "command": command,
                    "status": "success" if result.returncode == 0 else "error",
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            except Exception as e:
                results["main_result"] = {
                    "command": command,
                    "status": "error",
                    "error": str(e),
                }
            
            # Run cleanup commands
            if cleanup_commands:
                for cleanup_cmd in cleanup_commands:
                    try:
                        result = subprocess.run(
                            cleanup_cmd,
                            shell=True,
                            cwd=sandbox_work,
                            capture_output=True,
                            text=True,
                            timeout=self.timeout_seconds,
                            env=env,
                        )
                        results["cleanup_results"].append({
                            "command": cleanup_cmd,
                            "returncode": result.returncode,
                        })
                    except Exception as e:
                        results["cleanup_results"].append({
                            "command": cleanup_cmd,
                            "error": str(e),
                        })
        
        return results
    
    def rollback(self) -> Dict[str, Any]:
        """Rollback all tracked file changes."""
        if not self.file_tracker:
            return {"status": "error", "error": "File tracking not enabled"}
        
        rolled_back = self.file_tracker.rollback()
        self.file_tracker.clear()
        
        return {
            "status": "success",
            "rolled_back_files": rolled_back,
            "count": len(rolled_back),
        }
    
    def preview_command(self, command: str) -> Dict[str, Any]:
        """Preview what a command would do without executing."""
        blocked, reason = self.policy.is_blocked(command)
        
        return {
            "command": command,
            "blocked": blocked,
            "block_reason": reason,
            "is_safe": self.policy.is_safe(command),
            "modifies_files": self.policy.modifies_files(command),
            "would_sandbox": not self.policy.is_safe(command),
            "rollback_available": self.policy.modifies_files(command) and self.track_files,
        }


class TestShellRunner:
    """
    Test runner for shell commands with automatic cleanup.
    
    Useful for integration tests that need to run real commands
    but want automatic rollback of changes.
    """
    
    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = working_dir or tempfile.mkdtemp(prefix="test_shell_")
        self.executor = SafeShellExecutor(
            working_dir=self.working_dir,
            track_files=True,
        )
        self._created_temp = working_dir is None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
    
    def run(self, command: str) -> Dict[str, Any]:
        """Run command and track changes."""
        return self.executor.run(command, dry_run=False)
    
    def run_and_verify(
        self,
        command: str,
        expected_returncode: int = 0,
        expected_stdout_contains: Optional[str] = None,
        expected_stderr_contains: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run command and verify expected output."""
        result = self.run(command)
        
        result["verification"] = {
            "returncode_match": result.get("returncode") == expected_returncode,
            "stdout_match": True,
            "stderr_match": True,
        }
        
        if expected_stdout_contains:
            result["verification"]["stdout_match"] = (
                expected_stdout_contains in result.get("stdout", "")
            )
        
        if expected_stderr_contains:
            result["verification"]["stderr_match"] = (
                expected_stderr_contains in result.get("stderr", "")
            )
        
        result["verification"]["passed"] = all(result["verification"].values())
        
        return result
    
    def rollback(self) -> Dict[str, Any]:
        """Rollback all changes."""
        return self.executor.rollback()
    
    def cleanup(self):
        """Clean up test environment."""
        self.rollback()
        if self._created_temp and os.path.exists(self.working_dir):
            shutil.rmtree(self.working_dir, ignore_errors=True)


def create_safe_shell(
    allow_sudo: bool = False,
    allow_network: bool = True,
    track_files: bool = True,
    timeout: int = 30,
) -> SafeShellExecutor:
    """Factory function to create a configured safe shell executor."""
    policy = CommandPolicy(
        allow_sudo=allow_sudo,
        allow_network=allow_network,
    )
    return SafeShellExecutor(
        policy=policy,
        track_files=track_files,
        timeout_seconds=timeout,
    )
