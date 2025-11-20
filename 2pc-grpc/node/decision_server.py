# node/decision_server.py
import os
import time
from concurrent import futures
import grpc
import tx_pb2
import tx_pb2_grpc

NODE_ID = os.environ.get("NODE_ID", "nodeX")
DECISION_PORT = int(os.environ.get("DECISION_PORT", "60051"))

class DecisionServicer(tx_pb2_grpc.ParticipantServicer):
    # We use Decide here for final decision; Vote may be left as a stub.
    def Vote(self, request, context):
        # This service isn't the vote-phase, but implement a simple log
        print(f"Phase Participant-Decision of Node {NODE_ID} receives Vote RPC from Phase Coordinator of Node {request.from_node}")
        # Relay a VOTE_COMMIT for safety if called directly
        return tx_pb2.VoteResponse(node_id=NODE_ID, vote=tx_pb2.VOTE_COMMIT)

    def Decide(self, request, context):
        # Server-side print as required
        print(f"Phase Participant-Decision of Node {NODE_ID} sends RPC Decide to Phase Coordinator of Node coordinator")
        # Act upon decision
        if request.decision == tx_pb2.GLOBAL_COMMIT:
            print(f"Participant-Decision Node {NODE_ID}: committing transaction (tx ack from coordinator).")
        else:
            print(f"Participant-Decision Node {NODE_ID}: aborting transaction (tx ack from coordinator).")
        return tx_pb2.Ack(node_id=NODE_ID, decision=request.decision)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    tx_pb2_grpc.add_ParticipantServicer_to_server(DecisionServicer(), server)
    server.add_insecure_port(f"[::]:{DECISION_PORT}")
    print(f"Participant Decision server for {NODE_ID} starting on port {DECISION_PORT}")
    server.start()
    try:
        while True:
            time.sleep(60*60)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
