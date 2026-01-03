#!/bin/bash
# Simple script to run the game object editor

cd "$(dirname "$0")"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

# Run the editor
python3 game_object_editor.py


