import subprocess
import time
from datetime import datetime

PROJECT_DIR = r"E:\distributed-pv"
PYTHON = r"venv\Scripts\python.exe"

def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

nodes = [
    ("node1", "7001", "node2:localhost:7002,node3:localhost:7003,node4:localhost:7004,node5:localhost:7005"),
    ("node2", "7002", "node1:localhost:7001,node3:localhost:7003,node4:localhost:7004,node5:localhost:7005"),
    ("node3", "7003", "node1:localhost:7001,node2:localhost:7002,node4:localhost:7004,node5:localhost:7005"),
    ("node4", "7004", "node1:localhost:7001,node2:localhost:7002,node3:localhost:7003,node5:localhost:7005"),
    ("node5", "7005", "node1:localhost:7001,node2:localhost:7002,node3:localhost:7003,node4:localhost:7004"),
]

print(f"{ts()} 🔥 Starting 5 Raft nodes for Q3 election demo...")

for node_id, port, peers in nodes:
    cmd = f'{PYTHON} -m raft.raft_server --id={node_id} --port={port} --peers={peers}'

    print(f"{ts()} 🚀 Launching {node_id}")
    subprocess.Popen(
        f'start "{node_id}" cmd /k "{cmd}"',
        cwd=PROJECT_DIR,
        shell=True
    )
    time.sleep(0.5) 

