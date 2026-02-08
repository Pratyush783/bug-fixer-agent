from __future__ import annotations

import os
from typing import Optional

from tools import Tools, PermissionManager
from memory import ContextStore
from repo_utils import search_in_repo
from llm import LLMClient


class BugFixerAgent:
    """
    Conversational Bug Fixing Agent (CLI)

    Responsibilities:
    - Multi-turn conversation with the user
    - Bug analysis (LLM-assisted + heuristic fallback)
    - Summarize analysis BEFORE making changes
    - Apply fixes and add tests via tools
    - Permission-gated test execution
    - Final summarization
    """

    def __init__(self, tools: Tools, memory: ContextStore) -> None:
        self.tools = tools
        self.mem = memory
        self.llm = LLMClient()  # 🔹 LLM is optional and pluggable
        self.active_bug_id: Optional[str] = None

    # =========================
    # CLI UI LOOP
    # =========================
    def chat(self) -> None:
        print("Bug Fixer Agent (CLI)")
        print("Type 'help' for commands, 'exit' to quit.\n")

        while True:
            user = input("You: ").strip()

            if user.lower() in ("exit", "quit"):
                print("Agent: Bye.")
                return

            if user.lower() == "help":
                self._show_help()
                continue

            if user.lower() == "context":
                self._show_context()
                continue

            if user.lower() == "run-tests":
                self._run_tests_flow()
                continue

            self.mem.add_turn("user", user)
            self._handle_user_message(user)

    def _show_help(self) -> None:
        print(
            "\nCommands:\n"
            "  help        Show this help\n"
            "  context     Show internal agent context (debug)\n"
            "  run-tests   Execute tests (permission required)\n"
            "  exit        Quit the agent\n"
        )

    def _show_context(self) -> None:
        print("\n--- INTERNAL CONTEXT ---")
        print(self.mem.render_for_agent())
        print("--- END CONTEXT ---\n")

    # =========================
    # CONVERSATION HANDLING
    # =========================
    def _handle_user_message(self, user_msg: str) -> None:
        if self.active_bug_id is None:
            bug = self.mem.new_bug(user_report=user_msg)
            self.active_bug_id = bug.bug_id
            self._ask_clarifying(bug.bug_id)
            return

        self._analyze_and_propose(self.active_bug_id)

    def _ask_clarifying(self, bug_id: str) -> None:
        msg = (
            f"I’ve logged this as {bug_id}.\n"
            "Before I proceed:\n"
            "1) What is the expected behavior?\n"
            "2) Should the app raise an error, return a value, or handle it silently?\n"
        )
        self.mem.add_turn("agent", msg)
        print(f"Agent: {msg}")

    # =========================
    # ANALYSIS (LLM + FALLBACK)
    # =========================
    def _analyze_and_propose(self, bug_id: str) -> None:
        bug = next(b for b in self.mem.bugs if b.bug_id == bug_id)

        target_file = "demo_repo/src/calculator.py"
        ok, code = self.tools.read_file(target_file)
        if not ok:
            msg = f"Could not read {target_file}: {code}"
            self.mem.add_turn("agent", msg)
            print(f"Agent: {msg}")
            return

        root_cause = ""
        proposed_fix = ""

        #Attempt LLM-based reasoning FIRST
        llm_result = self.llm.analyze_bug(
            user_report=bug.user_report,
            code_snippet=code,
            file_path=target_file,
        )

        if llm_result:
            root_cause = llm_result["root_cause"]
            proposed_fix = llm_result["proposed_fix"]

        # 🔹 Deterministic fallback if LLM unavailable
        if not root_cause:
            if "def divide" in code and "b == 0" not in code:
                root_cause = (
                    "The divide(a, b) function does not guard against b == 0, "
                    "leading to a ZeroDivisionError at runtime."
                )
                proposed_fix = (
                    "Add an explicit check for b == 0 and raise a clear ValueError."
                )

        #Still uncertain → ask for more info
        if not root_cause:
            msg = (
                f"Bug analysis summary for {bug_id}:\n"
                f"- Suspected location: {target_file}\n"
                "- Root cause: Unable to confidently determine yet.\n"
                "- Proposed fix: Please provide the exact error or stack trace."
            )
            self.mem.add_turn("agent", msg)
            print(f"Agent: {msg}")
            return

        # Save bug state
        bug.root_cause = root_cause
        bug.proposed_fix = proposed_fix

        #REQUIRED: summarize BEFORE fixing
        analysis = (
            f"Bug analysis summary for {bug_id}:\n"
            f"- Location: {target_file}\n"
            f"- Root cause: {root_cause}\n"
            f"- Proposed fix: {proposed_fix}\n\n"
            "If this looks good, I will apply the fix, add tests, "
            "and then ask permission before running pytest."
        )

        self.mem.add_turn("agent", analysis)
        print(f"Agent: {analysis}")

        # Auto-proceed for demo purposes
        self._implement_fix_and_tests(bug_id)

    # =========================
    # FIX + TESTS
    # =========================
    def _implement_fix_and_tests(self, bug_id: str) -> None:
        bug = next(b for b in self.mem.bugs if b.bug_id == bug_id)

        target_file = "demo_repo/src/calculator.py"
        ok, code = self.tools.read_file(target_file)
        if not ok:
            print(f"Agent: Failed to read {target_file}")
            return

        if "b == 0" not in code:
            updated = code.replace(
                "def divide(a: float, b: float) -> float:\n    return a / b\n",
                "def divide(a: float, b: float) -> float:\n"
                "    if b == 0:\n"
                "        raise ValueError(\"Cannot divide by zero\")\n"
                "    return a / b\n",
            )
            self.tools.edit_file(target_file, updated)
            bug.files_changed.append(target_file)

        test_file = "demo_repo/tests/test_calculator.py"
        ok, tests = self.tools.read_file(test_file)
        if not ok:
            tests = ""

        if "test_divide_by_zero" not in tests:
            tests += (
                "\n\nimport pytest\n"
                "from src.calculator import divide\n\n"
                "def test_divide_by_zero():\n"
                "    with pytest.raises(ValueError):\n"
                "        divide(10, 0)\n"
            )
            self.tools.write_file(test_file, tests)
            bug.tests_added.append(test_file)

        msg = (
            "Fix applied and tests added.\n"
            "Type 'run-tests' to execute tests (permission required)."
        )
        self.mem.add_turn("agent", msg)
        print(f"Agent: {msg}")

    # =========================
    # TEST EXECUTION
    # =========================
    def _run_tests_flow(self) -> None:
        result = self.tools.bash("pytest -q")

        summary = "PASS" if result.ok else "FAIL"
        if self.mem.bugs:
            self.mem.bugs[-1].test_command = result.command
            self.mem.bugs[-1].test_result_summary = summary

        print("\nAgent: Test results:", summary)
        print(result.stdout or result.stderr)

        if result.ok:
            self._final_summary()

    # =========================
    # FINAL SUMMARY
    # =========================
    def _final_summary(self) -> None:
        lines = ["Final Summary:"]
        for bug in self.mem.bugs:
            lines.extend(
                [
                    f"- {bug.bug_id}: {bug.user_report}",
                    f"  Root cause: {bug.root_cause}",
                    f"  Fix: {bug.proposed_fix}",
                    f"  Files changed: {bug.files_changed}",
                    f"  Tests added: {bug.tests_added}",
                    f"  Test status: {bug.test_result_summary}",
                ]
            )

        msg = "\n".join(lines)
        self.mem.add_turn("agent", msg)
        print(f"\nAgent: {msg}\n")


# =========================
# ENTRY POINT
# =========================
def main() -> None:
    root_dir = os.path.abspath(".")
    permission = PermissionManager()
    tools = Tools(permission=permission, root_dir=root_dir)
    memory = ContextStore(token_limit=8000)

    agent = BugFixerAgent(tools=tools, memory=memory)
    agent.chat()


if __name__ == "__main__":
    main()
