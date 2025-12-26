#!/bin/bash

# Configuration
VENV_DIR="venv"
REQUIREMENTS="requirements.txt"
SCRIPT_NAME="viewer.py"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== LearnUs Backup Viewer ===${NC}"

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Python 3 could not be found. Please install Python 3."
    exit 1
fi

# Create Virtual Environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${GREEN}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Activate Virtual Environment
source "$VENV_DIR/bin/activate"

# Install Dependencies (Quietly to check if correct)
if [ -f "$REQUIREMENTS" ]; then
    pip install -r "$REQUIREMENTS" > /dev/null 2>&1
else
    echo "requirements.txt not found! Please run the setup script first."
    exit 1
fi

echo -e "${GREEN}Starting Viewer...${NC}"
echo -e "Open your browser to: http://localhost:5000"

# Run Viewer Script
python3 "$SCRIPT_NAME"
