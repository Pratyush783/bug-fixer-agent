from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


def approx_tokens(text: str) -> int:
    # Simple heuristic: ~4 chars per token
    return max(1, len(text) // 4)


@dataclass
class Turn:
    role: str  # "user" | "agent"
    content: str


@dataclass
class BugRecord:
    bug_id: str
    user_report: str
    expected_behavior: str = ""
    root_cause: str = ""
    proposed_fix: str = ""
    files_changed: List[str] = field(default_factory=list)
    tests_added: List[str] = field(default_factory=list)
    test_command: str = ""
    test_result_summary: str = ""


class ContextStore:
    """
    Stores:
      - conversation turns
      - structured bug records
      - compresses history when exceeding a simulated 8K token limit
    """
    def __init__(self, token_limit: int = 8000) -> None:
        self.token_limit = token_limit
        self.turns: List[Turn] = []
        self.summary: str = ""  # compressed older history
        self.bugs: List[BugRecord] = []
        self._bug_counter = 0

    def new_bug(self, user_report: str) -> BugRecord:
        self._bug_counter += 1
        bug = BugRecord(bug_id=f"BUG-{self._bug_counter:03d}", user_report=user_report)
        self.bugs.append(bug)
        return bug

    def add_turn(self, role: str, content: str) -> None:
        self.turns.append(Turn(role=role, content=content))
        self._maybe_compress()

    def total_tokens(self) -> int:
        turns_text = "\n".join([f"{t.role}: {t.content}" for t in self.turns])
        return approx_tokens(self.summary) + approx_tokens(turns_text)

    def _maybe_compress(self) -> None:
        if self.total_tokens() <= self.token_limit:
            return

        # Compress oldest ~40% of turns into summary text
        cut = max(1, int(len(self.turns) * 0.4))
        old = self.turns[:cut]
        self.turns = self.turns[cut:]

        # Heuristic compression (in a real system, call LLM here)
        compressed_lines = []
        for t in old:
            line = t.content.strip().replace("\n", " ")
            if len(line) > 180:
                line = line[:180] + "…"
            compressed_lines.append(f"- {t.role}: {line}")

        addition = "Compressed history:\n" + "\n".join(compressed_lines) + "\n"
        self.summary = (self.summary + "\n" + addition).strip()

    def render_for_agent(self) -> str:
        """
        What the agent uses as context.
        """
        bug_state = []
        for b in self.bugs:
            bug_state.append(
                f"{b.bug_id}: report={b.user_report!r} expected={b.expected_behavior!r} "
                f"root_cause={b.root_cause!r} proposed_fix={b.proposed_fix!r} "
                f"files_changed={b.files_changed} tests_added={b.tests_added} "
                f"test_result={b.test_result_summary!r}"
            )

        turns_text = "\n".join([f"{t.role}: {t.content}" for t in self.turns])
        return (
            f"=== SUMMARY (compressed) ===\n{self.summary}\n\n"
            f"=== BUG TRACKER ===\n" + ("\n".join(bug_state) if bug_state else "(none)") + "\n\n"
            f"=== RECENT TURNS ===\n{turns_text}\n"
        )
