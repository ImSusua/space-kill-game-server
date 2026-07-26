#!/bin/bash
# Game Server Startup Script
# Servers bind to 0.0.0.0 and always return 172.21.26.128 to clients.

cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)"

echo "Starting game server..."
echo "  HTTP:  0.0.0.0:8080  (login + resources)"
echo "  Gate:  0.0.0.0:8100  (RPC communication)"
echo "  Scene: 0.0.0.0:8200  (scene sync)"
echo "  Client IP: 172.21.26.128"
echo ""

python3 server.py
