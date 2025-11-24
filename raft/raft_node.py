"""
(Simplified) Raft node implementation for Q3 (leader election) and Q4 (log replication).

This version matches the assignment description you summarized:

- RequestVote:
    { candidate_id, term }

- AppendEntries (used for both heartbeat and log replication):
    {
        leader_id,
        entries: list of <o, t, k>
            o: operation string from client
            t: term under which the current leader serves
            k: index of o in the leader's log
        commit_index: index c of the most recently committed operation
    }

Behavior:
- Q3 test (no client requests):
    * logs stay empty, so every AppendEntries prints entries=[]
      and commit_index=0.

- Q4 test (with client requests):
    * When the leader receives a client request, it appends a new
      log entry (PENDING) but does NOT immediately replicate.
    * On the next heartbeat, the full log (including the pending
      entries) is sent to followers via AppendEntries.
    * After a heartbeat round with majority ACK, leader advances
      commit_index and applies entries.
    * On the following heartbeat, followers receive commit_index > 0
      and apply the newly committed entries.
"""

import random
import threading
import time
from datetime import datetime
from typing import Dict, Optional, List

import grpc
from concurrent import futures

from . import raft_pb2
from . import raft_pb2_grpc
from .state import RaftState, Role
from .log import make_log_entry, apply_entries


# ----------------------------------------------------------------------
# Helper for timestamped logs
# ----------------------------------------------------------------------
def ts(msg: str) -> str:
    """Return log line with millisecond timestamp."""
    return f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}"


def summarize_entries_dict(entries: List[dict]) -> str:
    """
    Summarize a list of dict log entries:
        {"index": k, "term": t, "operation": o}
    into: [(k=1,t=1,o='x'), ...]
    """
    if not entries:
        return "[]"
    parts = [f"(k={e['index']},t={e['term']},o='{e['operation']}')" for e in entries]
    return "[" + ", ".join(parts) + "]"


def summarize_entries_proto(entries: List[raft_pb2.LogEntry]) -> str:
    """
    Summarize a list of protobuf LogEntry objects.
    """
    if not entries:
        return "[]"
    parts = [f"(k={e.index},t={e.term},o='{e.operation}')" for e in entries]
    return "[" + ", ".join(parts) + "]"


# ----------------------------------------------------------------------
# Raft node
# ----------------------------------------------------------------------
class RaftNode(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, node_id: str, listen_addr: str, peers: Dict[str, str]):
        """
        :param node_id: logical node ID, e.g. "node1"
        :param listen_addr: address for this node, e.g. "localhost:7001"
        :param peers: mapping {peer_node_id: "host:port"}
        """
        self.node_id = node_id
        self.listen_addr = listen_addr
        self.peers = peers  # other node_id -> addr

        self.state = RaftState(node_id)
        self._stopped = threading.Event()
        self._grpc_server: Optional[grpc.Server] = None

        # Timeouts
        self.heartbeat_interval = 1.0            # Heartbeat every 1 second
        self.election_timeout_range = (5.0, 9.0) # Election timeout per node

        # Cluster size = self + peers
        self.cluster_size = len(self.peers) + 1

        # Heartbeat thread handle
        self._heartbeat_thread: Optional[threading.Thread] = None

        # Initial election timeout
        self._reset_election_deadline()

        print(ts(f"[INIT] Node {node_id} listening at {listen_addr}, peers = {list(peers.keys())}"))

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------
    def start(self):
        """Start gRPC server and election timer thread."""
        self._grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
        raft_pb2_grpc.add_RaftServiceServicer_to_server(self, self._grpc_server)
        self._grpc_server.add_insecure_port(self.listen_addr)
        self._grpc_server.start()

        # Election timer
        threading.Thread(target=self._run_election_timer, daemon=True).start()

        print(ts(f"[RUNNING] Node {self.node_id} gRPC server active -> {self.listen_addr}"))

    def wait_for_termination(self):
        if self._grpc_server:
            self._grpc_server.wait_for_termination()

    def stop(self):
        self._stopped.set()
        if self._grpc_server:
            self._grpc_server.stop(0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def is_leader(self) -> bool:
        return self.state.role == Role.LEADER

    def _reset_election_deadline(self):
        timeout = random.uniform(*self.election_timeout_range)
        self.state.election_deadline = time.time() + timeout

    # ------------------------------------------------------------------
    # Election timer
    # ------------------------------------------------------------------
    def _run_election_timer(self):
        while not self._stopped.is_set():
            time.sleep(0.1)

            trigger_election = False
            with self.state.lock:
                if self.state.role != Role.LEADER:
                    if time.time() > self.state.election_deadline:
                        trigger_election = True

            if trigger_election:
                print(ts(f"[TIMEOUT] Node {self.node_id} ({self.state.role}) election timeout, starting election"))
                self._start_election()

    # ------------------------------------------------------------------
    # Election logic
    # ------------------------------------------------------------------
    def _start_election(self):
        with self.state.lock:
            self.state.role = Role.CANDIDATE
            self.state.current_term += 1
            self.state.voted_for = self.node_id
            current_term = self.state.current_term
            votes = 1  # vote for self
            self._reset_election_deadline()

        print(ts(f"[ELECTION] Node {self.node_id} becomes candidate for term {current_term}"))

        # Send RequestVote to all peers
        for peer_id, addr in self.peers.items():
            try:
                print(ts(
                    f"Node {self.node_id} sends RPC RequestVote to Node {peer_id} "
                    f"with {{candidate_id={self.node_id}, term={current_term}}}"
                ))
                with grpc.insecure_channel(addr, options=[("grpc.enable_http_proxy", 0)]) as channel:
                    stub = raft_pb2_grpc.RaftServiceStub(channel)
                    response = stub.RequestVote(
                        raft_pb2.RequestVoteRequest(
                            candidate_id=self.node_id,
                            term=current_term,
                        ),
                        timeout=0.8,
                    )
                if response.vote_granted and response.term == current_term:
                    votes += 1
                    print(ts(f"[VOTE] Node {peer_id} granted vote to {self.node_id} for term {current_term}"))
            except grpc.RpcError as e:
                print(ts(f"[RPC-FAIL] Node {self.node_id} -> Node {peer_id} RequestVote failed: {e}"))
            except Exception as e:
                print(ts(f"[RPC-FAIL] Node {self.node_id} -> Node {peer_id} RequestVote failed: {e}"))

        # Check majority
        if votes > self.cluster_size // 2:
            with self.state.lock:
                if self.state.current_term == current_term and self.state.role == Role.CANDIDATE:
                    self._become_leader_locked()
        else:
            print(ts(f"[ELECTION] Node {self.node_id} failed election for term {current_term} (votes={votes})"))
            with self.state.lock:
                self.state.role = Role.FOLLOWER
                self.state.voted_for = None
                self._reset_election_deadline()

    def _become_leader_locked(self):
        self.state.role = Role.LEADER
        self.state.leader_id = self.node_id
        print(ts(f"[LEADER] Node {self.node_id} elected leader for term {self.state.current_term}"))

        # Avoid duplicate heartbeat threads
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return

        self._heartbeat_thread = threading.Thread(
            target=self._send_heartbeats_loop,
            daemon=True,
        )
        self._heartbeat_thread.start()

    # ------------------------------------------------------------------
    # Heartbeats + log replication (single AppendEntries mechanism)
    # ------------------------------------------------------------------
    def _send_heartbeats_loop(self):
        """
        Leader periodically sends AppendEntries RPC to all followers.

        On each round:
          - Take a snapshot of current log and commit_index.
          - Send AppendEntries with full log and commit_index=c.
          - If majority ACK, advance commit_index to the end of the
            snapshot log and apply new entries locally.

        Q3 test (no client ops):
          - snapshot_log is empty, commit_index == 0
          - logs show entries=[] and commit_index=0.

        Q4 test (with client ops):
          - After a client op is appended, snapshot_log has entries
            and commit_index may still be smaller than len(log).
        """
        while not self._stopped.is_set():
            # Take snapshot under lock
            with self.state.lock:
                if self.state.role != Role.LEADER:
                    print(ts(f"[HEARTBEAT-STOP] Node {self.node_id} is no longer leader, stop heartbeat loop"))
                    return

                term = self.state.current_term
                commit_index_to_send = self.state.commit_index
                snapshot_log = list(self.state.log)
                commit_target_index = len(snapshot_log)
                entries_proto = [
                    raft_pb2.LogEntry(index=e["index"], term=e["term"], operation=e["operation"])
                    for e in snapshot_log
                ]
                entries_summary = summarize_entries_dict(snapshot_log)

            # Send AppendEntries to all followers
            success_count = 1  # leader itself
            for peer_id, addr in self.peers.items():
                try:
                    print(ts(
                        f"Node {self.node_id} sends RPC AppendEntries to Node {peer_id} "
                        f"with {{leader_id={self.node_id}, term={term}, "
                        f"entries={entries_summary}, commit_index={commit_index_to_send}}}"
                    ))
                    with grpc.insecure_channel(addr) as channel:
                        stub = raft_pb2_grpc.RaftServiceStub(channel)
                        request = raft_pb2.AppendEntriesRequest(
                            leader_id=self.node_id,
                            term=term,
                            entries=entries_proto,
                            commit_index=commit_index_to_send,
                        )
                        response = stub.AppendEntries(request, timeout=1.0)

                    if response.success:
                        success_count += 1
                    else:
                        print(ts(
                            f"[REPL] AppendEntries {self.node_id} -> {peer_id} rejected "
                            f"(their_term={response.term}, our_term={term})"
                        ))
                except grpc.RpcError as e:
                    print(ts(f"[RPC-FAIL] Heartbeat/Replication {self.node_id} -> {peer_id}: {e}"))
                except Exception as e:
                    print(ts(f"[RPC-FAIL] Heartbeat/Replication {self.node_id} -> {peer_id}: {e}"))

            # Try to advance commit index after this round
            with self.state.lock:
                if self.state.role == Role.LEADER and self.state.current_term == term:
                    if success_count > self.cluster_size // 2:
                        if commit_target_index > self.state.commit_index:
                            self.state.commit_index = commit_target_index
                            apply_entries(self.state, self.state.commit_index)
                            print(ts(
                                f"[COMMIT] Node {self.node_id} commits log entries up to index "
                                f"{self.state.commit_index}"
                            ))

            time.sleep(self.heartbeat_interval)

    # ------------------------------------------------------------------
    # RPC handlers
    # ------------------------------------------------------------------
    def RequestVote(self, request: raft_pb2.RequestVoteRequest, context) -> raft_pb2.RequestVoteResponse:
        print(ts(
            f"Node {self.node_id} runs RPC RequestVote called by Node {request.candidate_id} "
            f"with {{candidate_id={request.candidate_id}, term={request.term}}}"
        ))

        with self.state.lock:
            # Old term -> reject
            if request.term < self.state.current_term:
                return raft_pb2.RequestVoteResponse(
                    vote_granted=False,
                    term=self.state.current_term,
                )

            # Newer term -> step down
            if request.term > self.state.current_term:
                if self.state.role != Role.FOLLOWER:
                    print(ts(
                        f"[DOWNGRADE] Node {self.node_id} downgraded to FOLLOWER due to higher term "
                        f"from candidate {request.candidate_id}"
                    ))
                self.state.current_term = request.term
                self.state.role = Role.FOLLOWER
                self.state.voted_for = None
                self.state.leader_id = None
                self._reset_election_deadline()

            # Grant vote if not yet voted, or voted for same candidate
            if self.state.voted_for is None or self.state.voted_for == request.candidate_id:
                self.state.voted_for = request.candidate_id
                self._reset_election_deadline()
                return raft_pb2.RequestVoteResponse(
                    vote_granted=True,
                    term=self.state.current_term,
                )

            # Otherwise, already voted for someone else
            return raft_pb2.RequestVoteResponse(
                vote_granted=False,
                term=self.state.current_term,
            )

    def AppendEntries(self, request: raft_pb2.AppendEntriesRequest, context) -> raft_pb2.AppendEntriesResponse:
        entries_summary = summarize_entries_proto(list(request.entries))
        print(ts(
            f"Node {self.node_id} runs RPC AppendEntries called by Node {request.leader_id} "
            f"with {{leader_id={request.leader_id}, term={request.term}, "
            f"entries={entries_summary}, commit_index={request.commit_index}}}"
        ))

        with self.state.lock:
            # Reject old term
            if request.term < self.state.current_term:
                return raft_pb2.AppendEntriesResponse(
                    success=False,
                    term=self.state.current_term,
                )

            # Newer term or we weren't follower -> step down
            if request.term > self.state.current_term or self.state.role != Role.FOLLOWER:
                print(ts(
                    f"[DOWNGRADE] Node {self.node_id} accepts leader {request.leader_id} for term {request.term}"
                ))
                self.state.current_term = request.term
                self.state.role = Role.FOLLOWER
                self.state.leader_id = request.leader_id
                self._reset_election_deadline()
            else:
                # Same term & follower, just refresh timeout
                self.state.leader_id = request.leader_id
                self._reset_election_deadline()

            # Full-log replacement (assignment simplification)
            new_log: List[dict] = []
            for entry in request.entries:
                new_log.append(
                    {
                        "index": entry.index,
                        "term": entry.term,
                        "operation": entry.operation,
                    }
                )
            if new_log:
                self.state.log = new_log

            # Apply all operations up to commit_index
            if request.commit_index > self.state.commit_index:
                self.state.commit_index = min(request.commit_index, len(self.state.log))
                apply_entries(self.state, self.state.commit_index)

            return raft_pb2.AppendEntriesResponse(
                success=True,
                term=self.state.current_term,
            )

    def ClientRequest(self, request: raft_pb2.ClientOperationRequest, context) -> raft_pb2.ClientOperationResponse:
        """
        ClientRequest:
        - Non-leader: forward to leader if known.
        - Leader: append new PENDING log entry; next heartbeat will
          replicate & eventually commit it.
        """
        print(ts(
            f"Node {self.node_id} runs RPC ClientRequest called by Node {request.node_id} "
            f"with operation='{request.operation}'"
        ))

        # Not leader -> forward if we know the leader
        with self.state.lock:
            is_leader = self.is_leader()
            leader_id = self.state.leader_id
            leader_addr = self.peers.get(leader_id) if leader_id else None

        if not is_leader:
            if leader_id and leader_addr:
                print(ts(f"Node {self.node_id} forwards client request to leader {leader_id}"))
                try:
                    print(ts(
                        f"Node {self.node_id} sends RPC ClientRequest to Node {leader_id} "
                        f"(forwarded client op='{request.operation}')"
                    ))
                    with grpc.insecure_channel(leader_addr) as channel:
                        stub = raft_pb2_grpc.RaftServiceStub(channel)
                        forward_req = raft_pb2.ClientOperationRequest(
                            client_id=request.client_id,
                            node_id=self.node_id,
                            operation=request.operation,
                        )
                        resp = stub.ClientRequest(forward_req, timeout=2.0)
                    return resp
                except grpc.RpcError as e:
                    print(ts(f"[RPC-FAIL] Client forward {self.node_id} -> {leader_id}: {e}"))
                    return raft_pb2.ClientOperationResponse(
                        success=False,
                        result="Forward to leader failed.",
                        leader_id=leader_id or "",
                    )

            # Unknown leader
            return raft_pb2.ClientOperationResponse(
                success=False,
                result="No known leader; please retry later.",
                leader_id="",
            )

        # We are the leader: append new entry as PENDING
        with self.state.lock:
            new_index = len(self.state.log) + 1
            entry = make_log_entry(new_index, self.state.current_term, request.operation)
            self.state.log.append(entry)
            print(ts(
                f"[LOG] Node {self.node_id} (leader) appended entry "
                f"(k={new_index}, t={self.state.current_term}, o='{request.operation}') PENDING; "
                f"will be replicated on next heartbeat"
            ))

        # In this simplified version we respond immediately; the commit
        # actually happens after one or more heartbeat rounds.
        return raft_pb2.ClientOperationResponse(
            success=True,
            result=f"Operation '{request.operation}' accepted by leader {self.node_id}, pending commit",
            leader_id=self.node_id,
        )
    
    
