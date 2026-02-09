from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import your existing code
from tools import Tools, ToolError
from memory import ContextStore
from tools import PermissionManager as CliPermissionManager  # not used for web
from agent import BugFixerAgent  # uses Tools + ContextStore

# --- Web Permission State ---

@dataclass
class PendingBash:
    request_id: str
    command: str


class WebPermissionManager:
    """
    Replaces stdin-based permission with a web-driven pending request.
    Tools.bash() will call request(); here we just record a pending request
    and return False until user approves via /permission/respond.
    """
    def __init__(self) -> None:
        self.pending: Optional[PendingBash] = None
        self.last_decision: Optional[bool] = None

    def request(self, command: str) -> bool:
        # If there is a recorded decision, consume it and return it
        if self.last_decision is not None:
            decision = self.last_decision
            self.last_decision = None
            self.pending = None
            return decision

        # Otherwise create a pending request and deny execution for now
        if self.pending is None:
            self.pending = PendingBash(request_id=str(uuid.uuid4()), command=command)
        return False  # do NOT execute until approved


# --- Session Model ---

class SessionState:
    def __init__(self) -> None:
        self.permission = WebPermissionManager()
        self.tools = Tools(permission=self.permission, root_dir=".")
        self.memory = ContextStore(token_limit=8000)
        self.agent = BugFixerAgent(tools=self.tools, memory=self.memory)
        self.latest_diff: str = ""
        self.latest_test_output: str = ""


SESSIONS: Dict[str, SessionState] = {}

# --- FastAPI app ---

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Schemas ---

class CreateSessionResp(BaseModel):
    session_id: str

class ChatReq(BaseModel):
    session_id: str
    message: str

class ChatResp(BaseModel):
    type: str  # "message" | "permission_request"
    agent_message: str
    diff: Optional[str] = None
    test_output: Optional[str] = None
    request_id: Optional[str] = None
    command: Optional[str] = None

class PermissionRespReq(BaseModel):
    session_id: str
    request_id: str
    approved: bool

# --- Helpers to capture diff/test output ---
# Your Tools.edit_file prints diff. For web UI, we want to return it.
# Minimal approach: read the file changes from stdout isn't easy without refactor.
# Easiest interview-safe approach: add a "last_diff" buffer in Tools.edit_file in the future.
# For now, we keep placeholders.

def get_session(session_id: str) -> SessionState:
    if session_id not in SESSIONS:
        SESSIONS[session_id] = SessionState()
    return SESSIONS[session_id]


@app.post("/session", response_model=CreateSessionResp)
def create_session() -> CreateSessionResp:
    sid = str(uuid.uuid4())
    SESSIONS[sid] = SessionState()
    return CreateSessionResp(session_id=sid)


@app.post("/chat", response_model=ChatResp)
def chat(req: ChatReq) -> ChatResp:
    s = get_session(req.session_id)

    # Route message into agent the same way CLI does:
    # We mimic the CLI by directly calling internal handlers.
    s.memory.add_turn("user", req.message)

    # Special: allow "run-tests" from UI
    if req.message.strip().lower() == "run-tests":
        # This triggers tools.bash("pytest -q") internally which will create a pending permission request
        s.agent._run_tests_flow()  # yes, private method, but fine for demo
    else:
        s.agent._handle_user_message(req.message)

    # If a permission request is pending, return it to frontend
    if s.permission.pending is not None:
        pb = s.permission.pending
        return ChatResp(
            type="permission_request",
            agent_message=(
                "To validate this, I need to run tests.\n"
                "Permission Request: May I execute this bash command?"
            ),
            request_id=pb.request_id,
            command=pb.command,
            diff=s.latest_diff or None,
            test_output=s.latest_test_output or None,
        )

    # Otherwise return last agent turn
    last_agent = next((t.content for t in reversed(s.memory.turns) if t.role == "agent"), "")
    return ChatResp(
        type="message",
        agent_message=last_agent or "(no response)",
        diff=s.latest_diff or None,
        test_output=s.latest_test_output or None,
    )


@app.post("/permission/respond", response_model=ChatResp)
def permission_respond(req: PermissionRespReq) -> ChatResp:
    s = get_session(req.session_id)

    # Validate request_id
    if not s.permission.pending or s.permission.pending.request_id != req.request_id:
        return ChatResp(
            type="message",
            agent_message="No matching permission request found.",
        )

    # Record decision
    s.permission.last_decision = req.approved

    if not req.approved:
        return ChatResp(
            type="message",
            agent_message="Understood — I will not execute that bash command.",
        )

    # Re-run the test flow: now request() will return True and bash will execute
    s.agent._run_tests_flow()

    last_agent = next((t.content for t in reversed(s.memory.turns) if t.role == "agent"), "")
    return ChatResp(
        type="message",
        agent_message=last_agent or "Tests executed.",
        diff=s.latest_diff or None,
        test_output=s.latest_test_output or None,
    )
