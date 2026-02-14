#!/bin/bash
# start.sh - Start script for LM Studio Proxy

# Check if virtual environment exists, if not create it
test -d ".venv" || python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Upgrade pip and install requirements
pip install --upgrade pip
pip install -r requirements.txt

# Start the API
python -m main