#!/bin/bash

##############################################################################
# CLEAR EDGE Simple Label Creator - Local Startup Script
#
# This runs the label creator on your Mac - no cloud needed!
#
# Usage:
#   ./run-simple.sh
##############################################################################

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}CLEAR EDGE Label Creator${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > .env << 'EOF'
# Gemini AI API Key (REQUIRED)
GEMINI_API_KEY=AIzaSyBs9RRCTZYT99JgLpP3I7raixF3yJJwvO0

# Application
ENV=development
LOG_LEVEL=INFO
API_PORT=8000
API_HOST=127.0.0.1

# Google Drive (Optional - not needed for simple mode)
ROOT_FOLDER_ID=1dIThii6ccCgWg5UlnT-x0-Gd8RmY_knr
ROOT_FOLDER_NAME=Product Labels
EOF
    echo -e "${GREEN}✓ Created .env file${NC}"
fi

# Check if Python venv exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate venv
source venv/bin/activate

# Install/update dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Starting Label Creator...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Open your browser to: ${BLUE}http://localhost:8000${NC}"
echo ""
echo -e "Press ${YELLOW}Ctrl+C${NC} to stop"
echo ""

# Run the simple app
python -m uvicorn simple_app:app --host 127.0.0.1 --port 8000 --reload
