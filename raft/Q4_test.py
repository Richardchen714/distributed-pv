import time
from raft.raft_node import RaftNode
from raft.raft_integration import send_operation_to_raft

# Configuration for 5-node cluster
nodes_config = {
    "node1": "localhost:7001",
    "node2": "localhost:7002",
    "node3": "localhost:7003",
    "node4": "localhost:7004",
    "node5": "localhost:7005",
}

# Build peer mapping for each node
peers = {
    node_id: {peer_id: addr for peer_id, addr in nodes_config.items() if peer_id != node_id}
    for node_id in nodes_config
}

# Start all nodes (single-process debug mode)
nodes = []
for node_id, addr in nodes_config.items():
    node = RaftNode(node_id, addr, peers[node_id])
    node.start()
    nodes.append(node)

print("🚀 All nodes are up. Waiting for leader election...")
time.sleep(10)  # Wait for election to stabilize

# Detect leader
leader = None
for node in nodes:
    if node.state.role == node.state.role.LEADER:
        leader = node
        print(f"📢 Leader elected: {node.node_id}")
        break

if not leader:
    print("❌ Leader election failed!")
    exit()

print("\n🧪 Sending 3 client operations to test log replication...\n")
for i in range(1, 4):
    op = f"test_op_{i}"
    print(f"\n📩 Proposing operation: {op}")
    resp = send_operation_to_raft("localhost:7001", op)  # Send to any node
    print(f"  → Response: success={resp.success}, result={resp.result}")
    time.sleep(2)

print("\n📌 Final log state of each node:")
for node in nodes:
    with node.state.lock:
        print(f"🔹 {node.node_id} log = {node.state.log}")
        print(f"   executed_operations = {node.state.executed_operations}")
