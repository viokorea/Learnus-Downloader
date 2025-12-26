#!/bin/bash

# Configuration
VENV_DIR="venv"
REQUIREMENTS="requirements.txt"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== LearnUs Backup Tool Setup ===${NC}"

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

# Install Dependencies
if [ -f "$REQUIREMENTS" ]; then
    echo -e "${GREEN}Installing dependencies...${NC}"
    pip install -r "$REQUIREMENTS"
else
    echo "requirements.txt not found!"
    exit 1
fi

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${BLUE}Starting Application...${NC}"

# Run Main Script
python3 main.py
