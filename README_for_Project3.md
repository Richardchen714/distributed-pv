# README for Project 3

[TOC]

## Two-Phase Commit (2PC) with gRPC (Voting + Decision Phases)

This project extends the distributed-pv system by implementing a fully working Two-Phase Commit (2PC) protocol using gRPC.

It supports:
- Voting Phase (Q1)
- Decision Phase (Q2)
- Cross-language compatibility by using a shared .proto file
- 5+ containerized nodes that communicate over gRPC
- A coordinator that runs the full 2PC protocol and logs all RPC calls

Each node runs two internal services:
1. Participant-Vote Phase Service
2. Participant-Decision Phase Service

Both services are gRPC servers running inside the same container, communicating only through gRPC.

## Overview of the Two-Phase Commit Protocol

A 2PC transaction has two phases:

### Phase 1 — Voting Phase

The Coordinator sends a Vote RPC request to all participant nodes.
Each Participant responds with:
1. VOTE_COMMIT — ready to commit
2. VOTE_ABORT — cannot commit

This is implemented with the RPC method:

```scss
rpc Vote(TxRequest) returns (VoteResponse)
```

### Phase 2 — Decision Phase

1. Coordinator gathers all votes:
   - If all commit, send GLOBAL_COMMIT
   - If any abort, send GLOBAL_ABORT
2. Each participant receives the decision and:
   - Commits (if global commit)
   - Aborts (if global abort)

This phase uses:

```scss
rpc Decide(Ack) returns (Ack)
```

## Logging Requirements (Implemented)

Every RPC prints logs in exactly this format:

### Client side

```php-template
Phase <phase_name> of Node <node_id> sends RPC <rpc_name> to Phase <phase_name> of Node <node_id>
```

### Server side

```php-template
Phase <phase_name> of Node <node_id> sends RPC <rpc_name> to Phase <phase_name> of Node <node_id>
```

All vote and decision RPCs produce these logs automatically.

## Container Architecture

Each participant node runs two internal gRPC servers:
|Service|Port|	Purpose|
|--|--|--|
|vote_server.py|50051|Handles Vote phase
|decision_server.py|60051|Handles final decision|

Coordinator uses the same .proto and connects to each node at these ports.

## Configuration

Each node uses two environment variables:
|Variable|Purpose|
|-|-|
|`NODE_ID`|Identifies the node
|`VOTE`	|Either COMMIT or ABORT|
|`VOTE_PORT`	|Port of voting server|
|`DECISION_PORT`	|Port of decision server|

Example in `docker-compose.yml`:
```yml
environment:
  - NODE_ID=node4
  - VOTE=ABORT
```
You can force an abort by setting `VOTE=ABORT`.

## How to Run

1. Build images

From the root folder (2pc-grpc/):
```bash
docker-compose build
```
2. Start the system
```bash
docker-compose up
```

This launches:
- 5 participant nodes
- 1 coordinator

The coordinator waits a few seconds and automatically starts 2PC for transaction:
```
tx-001
```

3. Read the output logs

You will see messages such as:
- Voting Phase:
```
Phase Coordinator of Node coordinator sends RPC Vote to Phase Participant-Vote of Node node1
Phase Participant-Vote of Node node1 sends RPC Vote to Phase Coordinator of Node coordinator
Phase Coordinator of Node coordinator received VoteResponse from node1: VOTE_COMMIT
```
- Decision Phase:
```
Coordinator decision for tx tx-001: GLOBAL_ABORT
Phase Coordinator of Node coordinator sends RPC Decide to Phase Participant-Decision of Node node4
Phase Participant-Decision of Node node4 sends RPC Decide to Phase Coordinator of Node coordinator
Participant-Decision Node node4: aborting transaction (tx ack from coordinator).
```

### Changing Votes to Test Behavior
To simulate different outcomes, edit docker-compose.yml:
Example: make node4 abort
```yml
node4:
  environment:
    - VOTE=ABORT
```
Example: all commit
```yml
node4:
  environment:
    - VOTE=COMMIT
```
Then rebuild & restart:
```bash
docker-compose down -v
docker-compose up --build
```

## Expected Scenarios
|Node Votes|Coordinator Decision|Behavior|
|-|-|-|
|All COMMIT|GLOBAL_COMMIT|All participants commit|
|One or more ABORT|GLOBAL_ABORT|All participants abort|