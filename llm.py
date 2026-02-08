from __future__ import annotations

import os
from typing import Optional


class LLMClient:
    """
    Optional. If OPENAI_API_KEY is set, you can wire an LLM call.
    For the assignment, it's fine to keep a "no-LLM" deterministic fallback.
    """
    def __init__(self) -> None:
        self.enabled = bool(os.getenv("OPENAI_API_KEY"))

    def complete(self, system: str, prompt: str) -> str:
        # Keep a safe fallback so the project runs without external APIs
        if not self.enabled:
            return (
                "LLM disabled. Fallback mode.\n"
                "I will use heuristic analysis based on the code and failing tests."
            )

        # If you want: implement OpenAI call here (intentionally omitted to keep submission self-contained)
        return "LLM enabled but not implemented in this template."
