# raft/state.py
import threading
from enum import Enum
from typing import List, Dict, Any


class Role(str, Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class RaftState:
    """
    In-memory state of a Raft node.

    This is intentionally simplified, but still follows the Raft paper:
    - current_term
    - voted_for
    - log: list of {index, term, operation}
    - commit_index: highest log index known to be committed
    - last_applied: highest log index actually executed
    """

    def __init__(self, node_id: str):
        self.node_id: str = node_id

        # Persistent state
        self.current_term: int = 0
        self.voted_for: str | None = None
        self.log: List[Dict[str, Any]] = []

        # Volatile state
        self.commit_index: int = 0
        self.last_applied: int = 0

        self.role: Role = Role.FOLLOWER
        self.leader_id: str | None = None

        # Used by the election timer.
        self.election_deadline: float = 0.0

        # For demo: list of executed operations in order.
        self.executed_operations: List[str] = []

        # Concurrency control.
        self.lock = threading.RLock()
