# raft/raft_server.py
"""
Standalone Raft server entrypoint for multi-process testing (Q3/Q4 demo),
compatible with the latest RaftNode logic.

Usage (sample):
python -m raft.raft_server --id=node1 --port=7001 --peers=node2:localhost:7002,node3:localhost:7003
"""

import argparse
import os
import time
from raft.raft_node import RaftNode

from datetime import datetime

def ts(msg: str) -> str:
    return f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="Node ID, e.g., node1")
    parser.add_argument("--port", required=True, help="Port, e.g., 7001")
    parser.add_argument("--peers", default="", help="Comma list: nodeX:host:port")

    args = parser.parse_args()

    # listen_addr = f"localhost:{args.port}"


    if os.getenv("USE_DOCKER") == "1":
        listen_addr = f"0.0.0.0:{args.port}"
    else:
        listen_addr = f"localhost:{args.port}"


    peers = {}
    if args.peers.strip():
        for p in args.peers.split(","):
            pid, host, port = p.split(":")
            peers[pid] = f"{host}:{port}"

    from raft.state import RaftState
    print(ts(f"[SERVER] Starting RaftNode {args.id} at {listen_addr} with peers = {peers}"))

    node = RaftNode(args.id, listen_addr, peers)
    node.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(ts(f"\n[SERVER] Node {args.id} shutting down (CTRL+C received)."))
        node.stop()

if __name__ == "__main__":
    main()
