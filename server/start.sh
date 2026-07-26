#!/bin/bash
# Game Server Startup Script
# Usage:
#   ./start.sh          - Start in test mode (127.0.0.1)
#   ./start.sh prod     - Start in production mode (172.21.26.128)

cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)"

if [ "$1" = "prod" ]; then
    export SERVER_MODE=prod
    echo "Starting server in PRODUCTION mode (IP: 172.21.26.128)"
else
    export SERVER_MODE=test
    echo "Starting server in TEST mode (IP: 127.0.0.1)"
fi

python3 server.py
