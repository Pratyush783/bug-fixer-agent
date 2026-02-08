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
