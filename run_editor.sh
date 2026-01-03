#!/bin/bash
# Simple launcher script for the game object editor
# Can be run from anywhere in the project

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TOOLS_DIR="$SCRIPT_DIR/tools"

# Find python3
PYTHON3=""
for path in "/usr/bin/python3" "/usr/local/bin/python3" "/opt/homebrew/bin/python3" "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"; do
    if [ -f "$path" ]; then
        PYTHON3="$path"
        break
    fi
done

if [ -z "$PYTHON3" ]; then
    PYTHON3=$(which python3 2>/dev/null)
fi

if [ -z "$PYTHON3" ] || [ ! -f "$PYTHON3" ]; then
    echo "Error: Python 3 not found"
    exit 1
fi

# Set up virtual environment
VENV_DIR="$TOOLS_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python3"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_PYTHON" ]; then
    echo "Creating virtual environment..."
    "$PYTHON3" -m venv "$VENV_DIR" || exit 1
fi

# Install dependencies if needed
if ! "$VENV_PYTHON" -c "import toml" 2>/dev/null; then
    echo "Installing dependencies..."
    "$VENV_PYTHON" -m pip install --upgrade pip --quiet
    "$VENV_PYTHON" -m pip install -r "$TOOLS_DIR/requirements.txt" || exit 1
fi

# Change to tools directory and run
cd "$TOOLS_DIR" || exit 1
"$VENV_PYTHON" game_object_editor.py

