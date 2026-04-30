from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class SessionState:
    last_tool: str | None = None
    messages: deque[str] = field(default_factory=lambda: deque(maxlen=6))


_SESSIONS: dict[str, SessionState] = {}


def get_session_state(session_id: str) -> SessionState:
    state = _SESSIONS.get(session_id)
    if state is None:
        state = SessionState()
        _SESSIONS[session_id] = state
    return state


def record_session_turn(session_id: str, message: str, tool: str) -> None:
    state = get_session_state(session_id)
    state.messages.append(message)
    state.last_tool = tool
