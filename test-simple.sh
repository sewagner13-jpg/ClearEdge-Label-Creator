#!/bin/bash

##############################################################################
# Quick test script to verify simple_app.py is ready to run
##############################################################################

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}Testing Simple Label Creator Setup...${NC}"
echo ""

# Check Python version
echo -n "1. Checking Python version... "
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
    echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ Python 3.11+ required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

# Check if required system packages are installed
echo -n "2. Checking Tesseract OCR... "
if command -v tesseract &> /dev/null; then
    echo -e "${GREEN}✓ Installed${NC}"
else
    echo -e "${YELLOW}⚠ Not installed (brew install tesseract)${NC}"
fi

echo -n "3. Checking poppler-utils... "
if command -v pdftoppm &> /dev/null; then
    echo -e "${GREEN}✓ Installed${NC}"
else
    echo -e "${YELLOW}⚠ Not installed (brew install poppler)${NC}"
fi

# Check file structure
echo -n "4. Checking app/ directory... "
if [ -d "app" ] && [ -f "app/__init__.py" ]; then
    echo -e "${GREEN}✓ Exists${NC}"
else
    echo -e "${RED}✗ Missing${NC}"
    exit 1
fi

echo -n "5. Checking simple_app.py... "
if [ -f "simple_app.py" ]; then
    echo -e "${GREEN}✓ Exists${NC}"
else
    echo -e "${RED}✗ Missing${NC}"
    exit 1
fi

echo -n "6. Checking run-simple.sh... "
if [ -f "run-simple.sh" ] && [ -x "run-simple.sh" ]; then
    echo -e "${GREEN}✓ Executable${NC}"
else
    echo -e "${YELLOW}⚠ Making executable...${NC}"
    chmod +x run-simple.sh
fi

echo -n "7. Checking requirements.txt... "
if [ -f "requirements.txt" ]; then
    echo -e "${GREEN}✓ Exists${NC}"
else
    echo -e "${RED}✗ Missing${NC}"
    exit 1
fi

# Check Python syntax
echo -n "8. Validating Python syntax... "
if python3 -m py_compile simple_app.py 2>/dev/null; then
    echo -e "${GREEN}✓ Valid${NC}"
else
    echo -e "${RED}✗ Syntax error${NC}"
    exit 1
fi

# Check required modules exist
echo -n "9. Checking app modules... "
MISSING=""
for module in pdf_extract gemini_client schema label_stub config; do
    if [ ! -f "app/${module}.py" ]; then
        MISSING="$MISSING $module"
    fi
done

if [ -z "$MISSING" ]; then
    echo -e "${GREEN}✓ All present${NC}"
else
    echo -e "${RED}✗ Missing: $MISSING${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All checks passed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Ready to run:"
echo ""
echo "  ./run-simple.sh"
echo ""
echo "Then open: http://localhost:8000"
echo ""
