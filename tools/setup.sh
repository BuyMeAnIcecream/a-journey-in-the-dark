#!/bin/bash
# Setup script for Game Object Editor

echo "Setting up Game Object Editor..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

# Check if pip3 is available
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 not found. Please install pip3."
    exit 1
fi

echo "Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "Setup complete! You can now run the editor with:"
    echo "  python3 game_object_editor.py"
    echo "  or"
    echo "  ./run_editor.sh"
else
    echo ""
    echo "Setup failed. Please install dependencies manually:"
    echo "  pip3 install toml Pillow"
    exit 1
fi

