# raft/log.py
from typing import Dict, List, Any
from .state import RaftState


def make_log_entry(index: int, term: int, operation: str) -> Dict[str, Any]:
    """
    Construct a single log entry.
    """
    return {
        "index": index,
        "term": term,
        "operation": operation,
    }


import json
from datetime import datetime

def apply_entries(state: RaftState, up_to_index: int):
    while state.last_applied < up_to_index:
        state.last_applied += 1
        entry = state.log[state.last_applied - 1]
        op = entry["operation"]

        try:
            op_dict = json.loads(op)
            print(f"[APPLY] Node {state.node_id} executes:", op_dict)
        except json.JSONDecodeError:
            print(f"[APPLY] Node {state.node_id} executes raw:", op)

        state.executed_operations.append(op)

