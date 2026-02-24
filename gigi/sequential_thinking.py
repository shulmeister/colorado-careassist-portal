"""
Sequential Thinking Engine for Gigi

Structured thinking tool for complex investigations, debugging, planning,
or any multi-step reasoning. Supports revision of earlier thoughts and
branching into alternative hypotheses.

Port of the MCP Sequential Thinking server concept, adapted for Gigi's
tool execution model (in-memory, async, per-session).
"""

import asyncio
import time
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class ThoughtData:
    """A single step in a thought chain."""
    thought: str
    thought_number: int
    total_thoughts: int
    next_thought_needed: bool
    is_revision: bool = False
    revises_thought: Optional[int] = None
    branch_from_thought: Optional[int] = None
    branch_id: Optional[str] = None
    needs_more_thoughts: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Strip None optional fields for cleaner output
        return {k: v for k, v in d.items() if v is not None}


class _SessionState:
    """Per-session state container."""
    __slots__ = ("thought_history", "branches", "lock", "last_access")

    def __init__(self):
        self.thought_history: list[ThoughtData] = []
        self.branches: dict[str, list[ThoughtData]] = {}
        self.lock = asyncio.Lock()
        self.last_access: float = time.time()

    def touch(self):
        self.last_access = time.time()


class SequentialThinkingEngine:
    """
    Structured thinking for complex investigations.
    Stores thought chains with revision and branching.

    Sessions auto-expire after 30 minutes of inactivity.
    Thread-safe via asyncio.Lock per session.
    """

    SESSION_TIMEOUT = 30 * 60  # 30 minutes

    def __init__(self):
        self._sessions: dict[str, _SessionState] = {}
        self._global_lock = asyncio.Lock()

    async def _get_session(self, session_id: str) -> _SessionState:
        """Get or create a session, pruning expired ones."""
        async with self._global_lock:
            # Prune expired sessions
            now = time.time()
            expired = [
                sid for sid, s in self._sessions.items()
                if now - s.last_access > self.SESSION_TIMEOUT
            ]
            for sid in expired:
                del self._sessions[sid]

            # Get or create
            if session_id not in self._sessions:
                self._sessions[session_id] = _SessionState()
            session = self._sessions[session_id]
            session.touch()
            return session

    async def process_thought(self, session_id: str, input_data: dict) -> dict:
        """
        Main entry point. Validates input, stores thought, tracks branches.

        Args:
            session_id: Session identifier (e.g. "default", conversation_id)
            input_data: Dict with thought, thought_number, total_thoughts,
                       next_thought_needed, plus optional revision/branch fields.

        Returns:
            State dict with thought_number, total_thoughts, next_thought_needed,
            branches list, and thought_history_length.
        """
        session = await self._get_session(session_id)

        async with session.lock:
            # Validate required fields
            thought = input_data.get("thought", "")
            if not thought:
                return {"error": "thought is required"}

            thought_number = input_data.get("thought_number", 1)
            total_thoughts = input_data.get("total_thoughts", 1)
            next_thought_needed = input_data.get("next_thought_needed", False)

            # Auto-adjust total if we've exceeded it
            if thought_number > total_thoughts:
                total_thoughts = thought_number

            # Handle needs_more_thoughts flag — extend scope
            needs_more = input_data.get("needs_more_thoughts", False)
            if needs_more and thought_number >= total_thoughts:
                total_thoughts = thought_number + 2  # Give room for more

            # Build thought data
            td = ThoughtData(
                thought=thought,
                thought_number=thought_number,
                total_thoughts=total_thoughts,
                next_thought_needed=next_thought_needed,
                is_revision=input_data.get("is_revision", False),
                revises_thought=input_data.get("revises_thought"),
                branch_from_thought=input_data.get("branch_from_thought"),
                branch_id=input_data.get("branch_id"),
                needs_more_thoughts=needs_more,
            )

            # Store in history
            session.thought_history.append(td)

            # Track branches
            if td.branch_id:
                if td.branch_id not in session.branches:
                    session.branches[td.branch_id] = []
                session.branches[td.branch_id].append(td)

            return {
                "thought_number": thought_number,
                "total_thoughts": total_thoughts,
                "next_thought_needed": next_thought_needed,
                "branches": list(session.branches.keys()),
                "thought_history_length": len(session.thought_history),
            }

    async def get_summary(self, session_id: str) -> dict:
        """
        Returns the full thought chain for a session.

        Returns:
            Dict with thoughts list, branch details, and metadata.
        """
        session = await self._get_session(session_id)

        async with session.lock:
            if not session.thought_history:
                return {
                    "session_id": session_id,
                    "total_thoughts": 0,
                    "thoughts": [],
                    "branches": {},
                    "message": "No thoughts recorded in this session.",
                }

            thoughts = []
            for td in session.thought_history:
                entry = {
                    "step": td.thought_number,
                    "thought": td.thought,
                    "next_needed": td.next_thought_needed,
                }
                if td.is_revision:
                    entry["is_revision"] = True
                    if td.revises_thought is not None:
                        entry["revises_step"] = td.revises_thought
                if td.branch_id:
                    entry["branch"] = td.branch_id
                    if td.branch_from_thought is not None:
                        entry["branched_from_step"] = td.branch_from_thought
                thoughts.append(entry)

            branches = {}
            for bid, bthoughts in session.branches.items():
                branches[bid] = [
                    {"step": t.thought_number, "thought": t.thought}
                    for t in bthoughts
                ]

            return {
                "session_id": session_id,
                "total_thoughts": len(session.thought_history),
                "estimated_total": session.thought_history[-1].total_thoughts,
                "thoughts": thoughts,
                "branches": branches,
            }

    async def clear_session(self, session_id: str) -> None:
        """Remove a session and free memory."""
        async with self._global_lock:
            self._sessions.pop(session_id, None)


# Module-level singleton
_engine = SequentialThinkingEngine()


async def sequential_thinking(
    thought: str,
    thought_number: int,
    total_thoughts: int,
    next_thought_needed: bool,
    session_id: str = "default",
    is_revision: bool = False,
    revises_thought: int = None,
    branch_from_thought: int = None,
    branch_id: str = None,
    needs_more_thoughts: bool = False,
) -> dict:
    """
    Process a thinking step. Returns state dict.

    This is the entry point called by execute_tool.
    """
    return await _engine.process_thought(session_id, {
        "thought": thought,
        "thought_number": thought_number,
        "total_thoughts": total_thoughts,
        "next_thought_needed": next_thought_needed,
        "is_revision": is_revision,
        "revises_thought": revises_thought,
        "branch_from_thought": branch_from_thought,
        "branch_id": branch_id,
        "needs_more_thoughts": needs_more_thoughts,
    })


async def get_thinking_summary(session_id: str = "default") -> dict:
    """Get the full thought chain for a session."""
    return await _engine.get_summary(session_id)
