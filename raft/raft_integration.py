# raft/raft_integration.py
"""
Thin helper functions to interact with the Raft cluster from the
Distributed Password Vault project.

You can import `send_operation_to_raft` from other modules to use Raft as
the consensus / log replication layer.
"""

import os
import uuid
from typing import Optional

import grpc

from . import raft_pb2, raft_pb2_grpc


def send_operation_to_raft(
    node_addr: str,
    operation: str,
    client_id: Optional[str] = None,
) -> raft_pb2.ClientOperationResponse:
    """
    Send a single logical operation to a Raft node.

    The receiver will either:
      - handle it directly if it is the leader, or
      - forward it to the leader, or
      - reply with an error if leader is unknown.

    :param node_addr: address of some node in the cluster, e.g. "localhost:7001"
    :param operation: operation string (your own format, e.g. JSON)
    :param client_id: optional client id; auto generated if None.
    """
    if client_id is None:
        client_id = str(uuid.uuid4())

    print(f"[CLIENT] Sending operation '{operation}' to {node_addr} as client {client_id}")
    with grpc.insecure_channel(node_addr) as channel:
        stub = raft_pb2_grpc.RaftServiceStub(channel)
        request = raft_pb2.ClientOperationRequest(
            client_id=client_id,
            node_id="client",  # for logging purposes
            operation=operation,
        )
        response = stub.ClientRequest(request, timeout=5.0)
    return response

def propose_operation(operation: str):
    """
    Wrapper for send_operation_to_raft().
    Returns (success_flag, message or index).
    """
    try:
        RAFT_NODE_ADDR = os.getenv("RAFT_NODE_ADDR", "raft-node1:7001")
        response = send_operation_to_raft(RAFT_NODE_ADDR, operation)

        if not response.success:
            return False, f"Rejected: {response.message}"

        return True, response.commit_index  # or response.log_index

    except Exception as e:
        return False, f"Error: {str(e)}"
