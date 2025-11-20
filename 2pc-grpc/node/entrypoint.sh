#!/bin/bash
set -e
# Start vote server and decision server in background
python /app/vote_server.py &
python /app/decision_server.py &
# Wait forever (or run a simple tail)
tail -f /dev/null
