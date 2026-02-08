# Bug Fixer Agent (CLI)

A conversational bug-fixing agent that:
- Discusses bugs with the user (multi-turn)
- Reads/edits/writes files via mandatory tools
- Writes tests and can run them
- Requests explicit permission before every bash command
- Maintains context + compresses when exceeding a simulated 8K limit
- Summarizes analysis before fixing and summarizes test results + final outcome

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

## LLM Integration

The agent supports optional LLM-based reasoning.

- Default mode: deterministic heuristic analysis (no external APIs)
- LLM mode: enabled automatically if `OPENAI_API_KEY` is set

The LLM is used **only for reasoning**:
- Root cause identification
- Fix proposal

All file edits and shell commands are still executed exclusively through
permission-gated tools (`read_file`, `edit_file`, `write_file`, `bash`).

At no point can the LLM execute code directly.

