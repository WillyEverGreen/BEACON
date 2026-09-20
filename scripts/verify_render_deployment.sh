#!/bin/bash
# Verify Render backend deployment is working correctly

set -e

echo "==========================================="
echo "BEACON Render Deployment Verification"
echo "==========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if BACKEND_URL is provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage: $0 <backend-url> [api-key]${NC}"
    echo "Example: $0 https://beacon-api.onrender.com your-admin-key"
    exit 1
fi

BACKEND_URL="$1"
API_KEY="${2:-}"

echo "Testing backend at: $BACKEND_URL"
echo ""

PASSED=0
FAILED=0

# Function to test endpoint
test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="$3"
    local headers="$4"
    
    echo -n "Testing $name... "
    
    if [ -n "$headers" ]; then
        response=$(curl -s -w "\n%{http_code}" -H "$headers" "$url" 2>&1)
    else
        response=$(curl -s -w "\n%{http_code}" "$url" 2>&1)
    fi
    
    status=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $status)"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected $expected_status, got $status)"
        echo "Response: $body"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# 1. Liveness Check
echo "=== Health Checks ==="
test_endpoint "Liveness" "$BACKEND_URL/health/live" "200"

# 2. Readiness Check
test_endpoint "Readiness" "$BACKEND_URL/health/ready" "200"

# 3. Audit Runtime Health
test_endpoint "Audit Health" "$BACKEND_URL/health/audit" "200"

# 4. General Health
test_endpoint "General Health" "$BACKEND_URL/health" "200"

# 5. Config Endpoint
echo ""
echo "=== API Endpoints ==="
test_endpoint "Config" "$BACKEND_URL/v1/config" "200"

# 6. Test authentication (if API key provided)
if [ -n "$API_KEY" ]; then
    echo ""
    echo "=== Authentication ==="
    test_endpoint "Auth with API Key" "$BACKEND_URL/health" "200" "X-API-Key: $API_KEY"
    
    echo ""
    echo "=== Audit Endpoint (requires auditor key) ==="
    echo -n "Testing audit endpoint... "
    
    audit_response=$(curl -s -w "\n%{http_code}" \
        -X POST "$BACKEND_URL/v1/audit" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -d '{"url": "https://example.com", "scan_mode": "minimal"}' 2>&1)
    
    audit_status=$(echo "$audit_response" | tail -n 1)
    
    if [ "$audit_status" = "200" ] || [ "$audit_status" = "202" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $audit_status - Audit accepted)"
        PASSED=$((PASSED + 1))
    else
        echo -e "${YELLOW}⚠ SKIP${NC} (HTTP $audit_status - May require auditor role)"
    fi
else
    echo -e "${YELLOW}⚠ Skipping authentication tests (no API key provided)${NC}"
fi

# 7. Check CORS headers
echo ""
echo "=== CORS Configuration ==="
echo -n "Checking CORS headers... "

cors_response=$(curl -s -I -H "Origin: https://example.com" "$BACKEND_URL/health")

if echo "$cors_response" | grep -q "access-control-allow-origin"; then
    echo -e "${GREEN}✓ CORS headers present${NC}"
    PASSED=$((PASSED + 1))
else
    echo -e "${YELLOW}⚠ CORS headers not found${NC}"
    echo "This may be expected if CORS middleware is conditional"
fi

# 8. Check security headers
echo ""
echo "=== Security Headers ==="
echo -n "Checking security headers... "

security_headers=$(curl -s -I "$BACKEND_URL/health")

has_headers=0
if echo "$security_headers" | grep -q "x-content-type-options"; then
    has_headers=1
fi

if [ $has_headers -eq 1 ]; then
    echo -e "${GREEN}✓ Security headers present${NC}"
    PASSED=$((PASSED + 1))
else
    echo -e "${YELLOW}⚠ Security headers not detected${NC}"
    echo "Consider adding security headers middleware"
fi

# 9. Response time check
echo ""
echo "=== Performance ==="
echo -n "Checking response time... "

start_time=$(date +%s%N)
curl -s "$BACKEND_URL/health/live" > /dev/null
end_time=$(date +%s%N)

response_time=$(( (end_time - start_time) / 1000000 ))

if [ $response_time -lt 1000 ]; then
    echo -e "${GREEN}✓ Fast${NC} (${response_time}ms)"
    PASSED=$((PASSED + 1))
elif [ $response_time -lt 3000 ]; then
    echo -e "${YELLOW}⚠ Acceptable${NC} (${response_time}ms)"
else
    echo -e "${RED}✗ Slow${NC} (${response_time}ms)"
    FAILED=$((FAILED + 1))
fi

# Summary
echo ""
echo "==========================================="
echo "Summary"
echo "==========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo "Backend is ready for production use."
    exit 0
else
    echo -e "${RED}✗ Some checks failed.${NC}"
    echo "Review the failures above and fix before deploying."
    exit 1
fi
