#!/bin/bash
# Start the Seattle Regulatory RAG server and open the chat UI.
# Usage: ./start.sh

cd "$(dirname "$0")"
exec .venv/bin/python scripts/start.py
