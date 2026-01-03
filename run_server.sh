#!/bin/bash
# Run server on a specific port
# Usage: ./run_server.sh [port]
# Default port: 3000

PORT=${1:-3000}
echo "Starting server on port $PORT..."
cargo run -- $PORT

