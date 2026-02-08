# from __future__ import annotations

# import os
# from typing import Optional


# class LLMClient:
#     """
#     Optional. If OPENAI_API_KEY is set, you can wire an LLM call.
#     For the assignment, it's fine to keep a "no-LLM" deterministic fallback.
#     """
#     def __init__(self) -> None:
#         self.enabled = bool(os.getenv("OPENAI_API_KEY"))

#     def complete(self, system: str, prompt: str) -> str:
#         # Keep a safe fallback so the project runs without external APIs
#         if not self.enabled:
#             return (
#                 "LLM disabled. Fallback mode.\n"
#                 "I will use heuristic analysis based on the code and failing tests."
#             )

#         # If you want: implement OpenAI call here (intentionally omitted to keep submission self-contained)
#         return "LLM enabled but not implemented in this template."



from __future__ import annotations

import os
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LLMClient:
    """
    Thin abstraction over an LLM.
    - Reasoning only
    - No tool execution
    - No side effects
    """

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self.enabled = bool(api_key)
        self.client: Optional[OpenAI] = None

        if self.enabled:
            self.client = OpenAI(api_key=api_key)

    def analyze_bug(
        self,
        user_report: str,
        code_snippet: str,
        file_path: str,
    ) -> Optional[dict]:
        """
        Returns:
        {
          "root_cause": str,
          "proposed_fix": str
        }
        or None if LLM disabled
        """
        if not self.enabled or not self.client:
            return None

        system_prompt = (
            "You are a senior software engineer acting as a bug analysis agent.\n"
            "You must only analyze and propose fixes.\n"
            "Do NOT execute code.\n"
            "Do NOT suggest running shell commands.\n"
            "Be concise and precise."
        )

        user_prompt = f"""
Bug report:
{user_report}

File: {file_path}

Code:
{code_snippet}

Tasks:
1. Identify the root cause of the bug.
2. Propose a clean, maintainable fix.
"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()

        # VERY simple parsing (interview-friendly)
        root = ""
        fix = ""

        for line in content.splitlines():
            if line.lower().startswith("root cause"):
                root = line.split(":", 1)[-1].strip()
            if line.lower().startswith("proposed fix"):
                fix = line.split(":", 1)[-1].strip()

        if not root or not fix:
            return {
                "root_cause": content,
                "proposed_fix": "See analysis above.",
            }

        return {
            "root_cause": root,
            "proposed_fix": fix,
        }
