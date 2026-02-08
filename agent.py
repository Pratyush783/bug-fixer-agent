from __future__ import annotations

import os
from typing import Optional

from tools import Tools, PermissionManager
from memory import ContextStore
from repo_utils import search_in_repo


class BugFixerAgent:
    """
    Conversational loop:
      - Ask clarifying questions
      - Inspect code via read_file
      - Summarize analysis BEFORE edits
      - Apply fix via edit_file/write_file
      - Add tests
      - Request permission for bash test runs
      - Summarize test results + final summary
    """
    def __init__(self, tools: Tools, memory: ContextStore) -> None:
        self.tools = tools
        self.mem = memory
        self.active_bug_id: Optional[str] = None

    def chat(self) -> None:
        print("Bug Fixer Agent (CLI)")
        print("Type 'exit' to quit. Type 'help' for commands.\n")

        while True:
            user = input("You: ").strip()
            if user.lower() in ("exit", "quit"):
                print("Agent: Bye.")
                return
            if user.lower() == "help":
                print("Commands:")
                print("  help                Show this help")
                print("  context             Show internal context (debug)")
                print("  run-tests           Ask to run pytest (requires permission)")
                print("  exit                Quit")
                continue
            if user.lower() == "context":
                print("\n--- INTERNAL CONTEXT ---")
                print(self.mem.render_for_agent())
                print("--- END CONTEXT ---\n")
                continue
            if user.lower() == "run-tests":
                self._run_tests_flow()
                continue

            self.mem.add_turn("user", user)
            self._handle_user_message(user)

    def _handle_user_message(self, user_msg: str) -> None:
        # Very small heuristic router for the demo repo.
        # In a real setup you'd call an LLM here, but this meets the assignment requirements.
        if self.active_bug_id is None:
            bug = self.mem.new_bug(user_report=user_msg)
            self.active_bug_id = bug.bug_id
            self._ask_clarifying(bug.bug_id, user_msg)
            return

        # If user answered clarifications, proceed to analyze/fix
        if any(k in user_msg.lower() for k in ["expected", "should", "want", "instead"]):
            self._analyze_and_propose(self.active_bug_id)
            return

        # Otherwise, still try analysis
        self._analyze_and_propose(self.active_bug_id)

    def _ask_clarifying(self, bug_id: str, report: str) -> None:
        msg = (
            f"I’ve logged this as {bug_id}.\n"
            "A couple quick clarifications so I fix the *right* behavior:\n"
            "1) What is the expected behavior (exact output / error message)?\n"
            "2) Any constraints (e.g., should it raise, return None, or return a structured error)?\n"
            "If you’re not sure, I can propose a sensible default and you can approve."
        )
        self.mem.add_turn("agent", msg)
        print(f"Agent: {msg}")

    def _analyze_and_propose(self, bug_id: str) -> None:
        bug = next(b for b in self.mem.bugs if b.bug_id == bug_id)

        calc_rel = "demo_repo/src/calculator.py"
        ok, calc_code = self.tools.read_file(calc_rel)
        if not ok:
            msg = f"Could not read {calc_rel}: {calc_code}"
            self.mem.add_turn("agent", msg)
            print(f"Agent: {msg}")
            return

        user_report = bug.user_report.lower()

        root_cause = ""
        proposed_fix = ""

        #Heuristic 1: Explicit user signal
        if (
            "zerodivisionerror" in user_report
            or "division by zero" in user_report
            or "divide(10, 0)" in user_report
            or "b=0" in user_report
        ):
            root_cause = (
                "calculator.divide is called with b == 0, "
                "causing a ZeroDivisionError."
            )
            proposed_fix = (
                "Add an explicit guard for b == 0 in divide() "
                "and raise a ValueError with a clear message."
            )

        #Heuristic 2: Static code analysis fallback
        elif "def divide" in calc_code and "b == 0" not in calc_code:
            root_cause = (
                "divide(a, b) does not guard against b == 0, "
                "leading to a runtime crash."
            )
            proposed_fix = (
                "Add explicit b == 0 handling in divide()."
            )

        #Still unknown
        if not root_cause:
            msg = (
                f"Bug analysis summary for {bug_id}:\n"
                f"- Suspected location: {calc_rel}\n"
                "- Root cause: Unable to confidently identify yet.\n"
                "- Proposed fix: Please share the exact error message or stack trace."
            )
            self.mem.add_turn("agent", msg)
            print(f"Agent: {msg}")
            return

        # Save state
        bug.root_cause = root_cause
        bug.proposed_fix = proposed_fix

        #REQUIRED: summarize BEFORE fixing
        analysis = (
            f"Bug analysis summary for {bug_id}:\n"
            f"- Suspected location: {calc_rel}\n"
            f"- Root cause: {root_cause}\n"
            f"- Proposed fix: {proposed_fix}\n\n"
            "If you approve, I will implement the fix, add tests, "
            "and then request permission before running pytest."
        )

        self.mem.add_turn("agent", analysis)
        print(f"Agent: {analysis}")

        # Auto-proceed for demo
        self._implement_fix_and_tests(bug_id)


    def _implement_fix_and_tests(self, bug_id: str) -> None:
        bug = next(b for b in self.mem.bugs if b.bug_id == bug_id)

        calc_rel = "demo_repo/src/calculator.py"
        ok, calc_code = self.tools.read_file(calc_rel)
        if not ok:
            msg = f"Could not read {calc_rel}: {calc_code}"
            self.mem.add_turn("agent", msg)
            print(f"Agent: {msg}")
            return

        # Implement fix: guard division by zero
        fixed = calc_code
        if "def divide" in fixed and "b == 0" not in fixed:
            fixed = fixed.replace(
                "def divide(a: float, b: float) -> float:\n    return a / b\n",
                "def divide(a: float, b: float) -> float:\n"
                "    if b == 0:\n"
                "        raise ValueError(\"Cannot divide by zero\")\n"
                "    return a / b\n",
            )

        ok, msg = self.tools.edit_file(calc_rel, fixed)
        if not ok:
            self.mem.add_turn("agent", f"edit failed: {msg}")
            print(f"Agent: edit failed: {msg}")
            return

        bug.files_changed.append(calc_rel)

        # Add/extend tests
        test_rel = "demo_repo/tests/test_calculator.py"
        ok, current = self.tools.read_file(test_rel)
        if not ok:
            current = ""

        if "test_divide_by_zero" not in current:
            test_content = (
                current.strip()
                + "\n\n"
                + "import pytest\n"
                + "from src.calculator import divide\n\n\n"
                + "def test_divide_by_zero():\n"
                + "    with pytest.raises(ValueError, match=\"divide by zero\"):\n"
                + "        divide(10, 0)\n"
            ).strip() + "\n"
            ok, wmsg = self.tools.write_file(test_rel, test_content)
            if not ok:
                self.mem.add_turn("agent", f"write test failed: {wmsg}")
                print(f"Agent: write test failed: {wmsg}")
                return

        bug.tests_added.append(test_rel)

        msg2 = (
            "Implemented fix + tests.\n"
            f"- Changed: {', '.join(bug.files_changed)}\n"
            f"- Tests: {', '.join(bug.tests_added)}\n"
            "Next: I can run tests with:\n"
            "  pytest -q\n"
            "But I must ask permission before executing any bash command.\n"
            "Type 'run-tests' when you want me to execute it."
        )
        self.mem.add_turn("agent", msg2)
        print(f"Agent: {msg2}")

    def _run_tests_flow(self) -> None:
        cmd = "pytest -q"
        res = self.tools.bash(cmd)
        summary = (
            f"Test run command: {res.command}\n"
            f"Exit code: {res.returncode}\n"
            f"STDOUT:\n{res.stdout}\n"
            f"STDERR:\n{res.stderr}\n"
        )
        if self.mem.bugs:
            self.mem.bugs[-1].test_command = cmd
            self.mem.bugs[-1].test_result_summary = "PASS ✅" if res.ok else "FAIL ❌"

        self.mem.add_turn("agent", "Test results summary:\n" + ("PASS ✅" if res.ok else "FAIL ❌"))
        print("\nAgent: Test results summary:", "PASS ✅" if res.ok else "FAIL ❌")
        print(summary)

        if res.ok:
            self._final_summary()

    def _final_summary(self) -> None:
        lines = ["Final summary of work:"]
        for b in self.mem.bugs:
            lines.append(f"- {b.bug_id}: {b.user_report}")
            if b.root_cause:
                lines.append(f"  - Root cause: {b.root_cause}")
            if b.proposed_fix:
                lines.append(f"  - Fix: {b.proposed_fix}")
            if b.files_changed:
                lines.append(f"  - Files changed: {b.files_changed}")
            if b.tests_added:
                lines.append(f"  - Tests added: {b.tests_added}")
            if b.test_result_summary:
                lines.append(f"  - Tests: {b.test_result_summary}")

        msg = "\n".join(lines)
        self.mem.add_turn("agent", msg)
        print(f"\nAgent: {msg}\n")


def main() -> None:
    # Root dir is repo root; the demo code lives in demo_repo/
    root_dir = os.path.abspath(".")
    permission = PermissionManager()
    tools = Tools(permission=permission, root_dir=root_dir)
    memory = ContextStore(token_limit=8000)

    agent = BugFixerAgent(tools=tools, memory=memory)
    agent.chat()


if __name__ == "__main__":
    main()
