# node/vote_server.py
import os
import time
from concurrent import futures
import grpc
import tx_pb2
import tx_pb2_grpc

NODE_ID = os.environ.get("NODE_ID", "nodeX")
VOTE_DECISION = os.environ.get("VOTE", "COMMIT").upper()  # COMMIT or ABORT
VOTE_PORT = int(os.environ.get("VOTE_PORT", "50051"))

class ParticipantServicer(tx_pb2_grpc.ParticipantServicer):
    def Vote(self, request, context):
        # Server-side print as required
        print(f"Phase Participant-Vote of Node {NODE_ID} sends RPC Vote to Phase Coordinator of Node {request.from_node}")
        # Decide vote depending on env var
        vote_enum = tx_pb2.VOTE_COMMIT if VOTE_DECISION == "COMMIT" else tx_pb2.VOTE_ABORT
        # Also print server-side decision
        print(f"Phase Participant-Vote of Node {NODE_ID} returns vote {tx_pb2.Vote.Name(vote_enum)} for tx {request.tx_id}")
        return tx_pb2.VoteResponse(node_id=NODE_ID, vote=vote_enum)

    def Decide(self, request, context):
        # This server won't implement Decide (Decision service handles that),
        # but include for completeness in same proto.
        print(f"Phase Participant-Vote of Node {NODE_ID} sends RPC Decide to Phase Participant-Decision of Node {NODE_ID}")
        return tx_pb2.Ack(node_id=NODE_ID, decision=request.decision)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    tx_pb2_grpc.add_ParticipantServicer_to_server(ParticipantServicer(), server)
    server.add_insecure_port(f"[::]:{VOTE_PORT}")
    print(f"Participant Vote server for {NODE_ID} starting on port {VOTE_PORT} (vote = {VOTE_DECISION})")
    server.start()
    try:
        while True:
            time.sleep(60*60)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
