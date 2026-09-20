#!/bin/bash
# Verify frontend configuration before deployment

set -e

echo "========================================="
echo "BEACON Frontend Configuration Validator"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Check if frontend directory exists
if [ ! -d "frontend" ]; then
    echo -e "${RED}✗ frontend/ directory not found${NC}"
    exit 1
fi

cd frontend

echo "Checking frontend configuration..."
echo ""

# 1. Check if .env.local exists (for local dev)
if [ ! -f ".env.local" ] && [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ No .env.local or .env file found${NC}"
    echo "  Create one from .env.example for local development"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✓ Environment file found${NC}"
fi

# 2. Check if package.json exists
if [ ! -f "package.json" ]; then
    echo -e "${RED}✗ package.json not found${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓ package.json exists${NC}"
fi

# 3. Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠ node_modules not found. Run 'npm install'${NC}"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi

# 4. Check critical files
FILES_TO_CHECK=(
    "src/app/layout.tsx"
    "src/app/page.tsx"
    "src/lib/beaconProxy.ts"
    "next.config.ts"
    ".env.example"
)

echo ""
echo "Checking critical files..."
for file in "${FILES_TO_CHECK[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}✗ Missing: $file${NC}"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}✓ Found: $file${NC}"
    fi
done

# 5. Check TypeScript compilation
echo ""
echo "Checking TypeScript configuration..."
if command -v npm &> /dev/null; then
    if npm run build --dry-run &> /dev/null; then
        echo -e "${GREEN}✓ Build command configured${NC}"
    else
        echo -e "${YELLOW}⚠ Build command may have issues${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

# 6. Validate next.config.ts
echo ""
echo "Validating next.config.ts..."
if grep -q "validateEnv" "next.config.ts"; then
    echo -e "${GREEN}✓ Environment validation configured${NC}"
else
    echo -e "${YELLOW}⚠ Environment validation not found in next.config.ts${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

if grep -q "headers()" "next.config.ts"; then
    echo -e "${GREEN}✓ Security headers configured${NC}"
else
    echo -e "${YELLOW}⚠ Security headers not configured${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# 7. Check for common mistakes
echo ""
echo "Checking for common mistakes..."

if grep -r "console.log" src/ --include="*.ts" --include="*.tsx" | grep -v "console.error" | grep -v "console.warn" > /dev/null; then
    echo -e "${YELLOW}⚠ Found console.log statements in src/ (should be removed for production)${NC}"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✓ No console.log statements found${NC}"
fi

if [ -f ".env" ] || [ -f ".env.local" ]; then
    if git check-ignore .env > /dev/null 2>&1 && git check-ignore .env.local > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Environment files are in .gitignore${NC}"
    else
        echo -e "${RED}✗ Environment files may not be properly gitignored!${NC}"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Summary
echo ""
echo "========================================="
echo "Summary"
echo "========================================="

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Frontend is ready for deployment.${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ ${WARNINGS} warning(s) found. Review before deploying.${NC}"
    exit 0
else
    echo -e "${RED}✗ ${ERRORS} error(s) found. Fix before deploying.${NC}"
    [ $WARNINGS -gt 0 ] && echo -e "${YELLOW}⚠ ${WARNINGS} warning(s) also found.${NC}"
    exit 1
fi
