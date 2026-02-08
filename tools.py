from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple
import difflib


class ToolError(Exception):
    pass


@dataclass
class BashResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    command: str


class PermissionManager:
    """
    Enforces: NO bash command executes without explicit user permission.

    - Asks for approval each time by default
    - Supports "always allow for session" mode (still explicit)
    """
    def __init__(self) -> None:
        self.always_allow: bool = False

    def request(self, command: str) -> bool:
        if self.always_allow:
            return True

        print("\nPermission Request: May I execute this bash command?")
        print(f"Command: {command}")
        while True:
            ans = input("Approve? [y/N/a=always allow for session]: ").strip().lower()
            if ans in ("y", "yes"):
                return True
            if ans in ("a", "always"):
                self.always_allow = True
                return True
            if ans in ("", "n", "no"):
                return False
            print("Please type y / n / a.")


class Tools:
    """
    Implements the 4 required tools:
      - bash(command)
      - read_file(file_path)
      - write_file(file_path, content)
      - edit_file(file_path, changes)

    Design choice:
      - edit_file uses full-content replacement (the 'changes' argument is the new file content).
      - The CLI prints a unified diff for visibility.
    """
    def __init__(self, permission: PermissionManager, root_dir: str) -> None:
        self.permission = permission
        self.root_dir = os.path.abspath(root_dir)

    def _safe_path(self, file_path: str) -> str:
        abs_path = os.path.abspath(os.path.join(self.root_dir, file_path))
        if not abs_path.startswith(self.root_dir + os.sep) and abs_path != self.root_dir:
            raise ToolError(f"Unsafe path (outside root): {file_path}")
        return abs_path

    # 1) bash(command) — MUST ask permission first
    def bash(self, command: str, timeout_s: int = 60) -> BashResult:
        approved = self.permission.request(command)
        if not approved:
            return BashResult(
                ok=False,
                returncode=126,
                stdout="",
                stderr="User rejected bash command execution.",
                command=command,
            )

        # Execute only after approval
        proc = subprocess.run(
            command,
            shell=True,
            cwd=self.root_dir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return BashResult(
            ok=(proc.returncode == 0),
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            command=command,
        )

    # 2) read_file(file_path)
    def read_file(self, file_path: str) -> Tuple[bool, str]:
        try:
            abs_path = self._safe_path(file_path)
            if not os.path.exists(abs_path):
                return False, f"File not found: {file_path}"
            with open(abs_path, "r", encoding="utf-8") as f:
                return True, f.read()
        except Exception as e:
            return False, f"read_file error: {e}"

    # 3) write_file(file_path, content)
    def write_file(self, file_path: str, content: str) -> Tuple[bool, str]:
        try:
            abs_path = self._safe_path(file_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, f"Wrote {file_path} ({len(content)} bytes)."
        except Exception as e:
            return False, f"write_file error: {e}"

    # 4) edit_file(file_path, changes)
    def edit_file(self, file_path: str, changes: str) -> Tuple[bool, str]:
        try:
            ok, old = self.read_file(file_path)
            if not ok:
                return False, old

            # show diff for UI visibility
            diff = "\n".join(
                difflib.unified_diff(
                    old.splitlines(),
                    changes.splitlines(),
                    fromfile=f"a/{file_path}",
                    tofile=f"b/{file_path}",
                    lineterm="",
                )
            )
            print("\n--- Proposed Diff ---")
            print(diff if diff.strip() else "(No changes)")
            print("--- End Diff ---\n")

            return self.write_file(file_path, changes)
        except Exception as e:
            return False, f"edit_file error: {e}"
