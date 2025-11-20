# coordinator/coordinator.py
import os
import grpc
import time
from concurrent import futures
import tx_pb2
import tx_pb2_grpc

# Configure participants and ports; these should match docker-compose below
participants = [
    {"id": "node1", "vote_addr": "node1:50051", "decide_addr": "node1:60051"},
    {"id": "node2", "vote_addr": "node2:50051", "decide_addr": "node2:60051"},
    {"id": "node3", "vote_addr": "node3:50051", "decide_addr": "node3:60051"},
    {"id": "node4", "vote_addr": "node4:50051", "decide_addr": "node4:60051"},
    {"id": "node5", "vote_addr": "node5:50051", "decide_addr": "node5:60051"},
]

COORD_ID = "coordinator"

def send_vote_request(participant, tx_id):
    # Client-side print before RPC
    print(f"Phase Coordinator of Node {COORD_ID} sends RPC Vote to Phase Participant-Vote of Node {participant['id']}")
    channel = grpc.insecure_channel(participant["vote_addr"])
    stub = tx_pb2_grpc.ParticipantStub(channel)
    req = tx_pb2.TxRequest(tx_id=tx_id, from_node=COORD_ID)
    resp = stub.Vote(req, timeout=5)
    # client prints also result
    print(f"Phase Coordinator of Node {COORD_ID} received VoteResponse from Node {resp.node_id}: {tx_pb2.Vote.Name(resp.vote)}")
    return resp

def send_decision(participant, tx_id, decision):
    # Client-side print before RPC
    decision_name = tx_pb2.Decision.Name(decision)
    print(f"Phase Coordinator of Node {COORD_ID} sends RPC Decide to Phase Participant-Decision of Node {participant['id']}")
    channel = grpc.insecure_channel(participant["decide_addr"])
    stub = tx_pb2_grpc.ParticipantStub(channel)
    ack = tx_pb2.Ack(node_id=COORD_ID, decision=decision)
    resp = stub.Decide(ack, timeout=5)
    print(f"Phase Coordinator of Node {COORD_ID} received Ack from Node {resp.node_id} for decision {tx_pb2.Decision.Name(resp.decision)}")
    return resp

def run_2pc(tx_id="tx123"):
    # Voting phase
    votes = []
    for p in participants:
        try:
            r = send_vote_request(p, tx_id)
            votes.append(r)
        except Exception as e:
            print(f"Coordinator: error contacting {p['id']}: {e}")
            # Treat error as abort vote
            votes.append(tx_pb2.VoteResponse(node_id=p['id'], vote=tx_pb2.VOTE_ABORT))

    # Decision logic
    all_commit = all(v.vote == tx_pb2.VOTE_COMMIT for v in votes)
    decision = tx_pb2.GLOBAL_COMMIT if all_commit else tx_pb2.GLOBAL_ABORT
    print(f"Coordinator decision for tx {tx_id}: {tx_pb2.Decision.Name(decision)}")

    # send decision to all participants
    for p in participants:
        try:
            send_decision(p, tx_id, decision)
        except Exception as e:
            print(f"Coordinator: error sending decision to {p['id']}: {e}")

if __name__ == "__main__":
    # Wait a bit to allow participants to come up
    time.sleep(3)
    print("Coordinator starting 2PC")
    run_2pc("tx-001")
