#!/bin/bash
set -euo pipefail

# -----------------------------------------------------------------------
# BRAIN 3.0 — Smoke Test Script
# Validates the full API surface after deployment.
# Usage: ./scripts/smoke-test.sh [BASE_URL]
# -----------------------------------------------------------------------

BASE_URL="${1:-http://localhost:8000}"
PASSED=0
FAILED=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Cleanup tracking
DOMAIN_ID=""
GOAL_ID=""
PROJECT_ID=""
TASK_ID=""
ACTIVITY_ID=""

pass_step() {
    echo -e "  ${GREEN}PASS${NC}: $1"
    PASSED=$((PASSED + 1))
}

fail_step() {
    echo -e "  ${RED}FAIL${NC}: $1"
    [ -n "${2:-}" ] && echo "        $2"
    FAILED=1
    cleanup
    echo ""
    echo -e "${RED}Smoke test failed.${NC} $PASSED step(s) passed before failure."
    exit 1
}

cleanup() {
    echo ""
    echo "Cleaning up test entities..."
    [ -n "$ACTIVITY_ID" ] && curl -s -L -X DELETE "$BASE_URL/api/activity/$ACTIVITY_ID" > /dev/null 2>&1 && echo "  Deleted activity $ACTIVITY_ID" || true
    [ -n "$TASK_ID" ] && curl -s -L -X DELETE "$BASE_URL/api/tasks/$TASK_ID" > /dev/null 2>&1 && echo "  Deleted task $TASK_ID" || true
    [ -n "$PROJECT_ID" ] && curl -s -L -X DELETE "$BASE_URL/api/projects/$PROJECT_ID" > /dev/null 2>&1 && echo "  Deleted project $PROJECT_ID" || true
    [ -n "$GOAL_ID" ] && curl -s -L -X DELETE "$BASE_URL/api/goals/$GOAL_ID" > /dev/null 2>&1 && echo "  Deleted goal $GOAL_ID" || true
    [ -n "$DOMAIN_ID" ] && curl -s -L -X DELETE "$BASE_URL/api/domains/$DOMAIN_ID" > /dev/null 2>&1 && echo "  Deleted domain $DOMAIN_ID" || true
}

# Helper: make an API call and capture status + body
api_call() {
    local method="$1"
    local path="$2"
    local data="${3:-}"

    if [ -n "$data" ]; then
        RESPONSE=$(curl -s -L -w "\n%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$BASE_URL$path" 2>&1) || RESPONSE=$'error\n000'
    else
        RESPONSE=$(curl -s -L -w "\n%{http_code}" -X "$method" \
            "$BASE_URL$path" 2>&1) || RESPONSE=$'error\n000'
    fi

    BODY=$(echo "$RESPONSE" | sed '$d')
    HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
}

echo "============================================"
echo "  BRAIN 3.0 Smoke Test"
echo "  Target: $BASE_URL"
echo "============================================"
echo ""

# -----------------------------------------------------------------------
# Step 1: Health check
# -----------------------------------------------------------------------
echo "Step 1: Health check"
api_call GET /health

STATUS=$(echo "$BODY" | jq -r '.status' 2>/dev/null)
DB_STATUS=$(echo "$BODY" | jq -r '.database' 2>/dev/null)

if [ "$STATUS" = "healthy" ] && [ "$DB_STATUS" = "connected" ]; then
    pass_step "Health check — API healthy, database connected"
else
    fail_step "Health check" "Got status=$STATUS, database=$DB_STATUS"
fi

# -----------------------------------------------------------------------
# Step 2: Create domain
# -----------------------------------------------------------------------
echo "Step 2: Create domain"
api_call POST /api/domains '{"name": "Smoke Test Domain"}'

if [ "$HTTP_STATUS" = "201" ]; then
    DOMAIN_ID=$(echo "$BODY" | jq -r '.id')
    pass_step "Created domain $DOMAIN_ID"
else
    fail_step "Create domain" "Expected 201, got $HTTP_STATUS"
fi

# -----------------------------------------------------------------------
# Step 3: Read domain back
# -----------------------------------------------------------------------
echo "Step 3: Read domain"
api_call GET "/api/domains/$DOMAIN_ID"

NAME=$(echo "$BODY" | jq -r '.name' 2>/dev/null)
if [ "$HTTP_STATUS" = "200" ] && [ "$NAME" = "Smoke Test Domain" ]; then
    pass_step "Read domain — name matches"
else
    fail_step "Read domain" "Expected 200 with name 'Smoke Test Domain', got $HTTP_STATUS / $NAME"
fi

# -----------------------------------------------------------------------
# Step 4: Create goal under domain
# -----------------------------------------------------------------------
echo "Step 4: Create goal"
api_call POST /api/goals "{\"domain_id\": \"$DOMAIN_ID\", \"title\": \"Smoke Test Goal\"}"

if [ "$HTTP_STATUS" = "201" ]; then
    GOAL_ID=$(echo "$BODY" | jq -r '.id')
    pass_step "Created goal $GOAL_ID"
else
    fail_step "Create goal" "Expected 201, got $HTTP_STATUS"
fi

# -----------------------------------------------------------------------
# Step 5: Create project under goal
# -----------------------------------------------------------------------
echo "Step 5: Create project"
api_call POST /api/projects "{\"goal_id\": \"$GOAL_ID\", \"title\": \"Smoke Test Project\"}"

if [ "$HTTP_STATUS" = "201" ]; then
    PROJECT_ID=$(echo "$BODY" | jq -r '.id')
    pass_step "Created project $PROJECT_ID"
else
    fail_step "Create project" "Expected 201, got $HTTP_STATUS"
fi

# -----------------------------------------------------------------------
# Step 6: Create task under project
# -----------------------------------------------------------------------
echo "Step 6: Create task"
api_call POST /api/tasks "{\"project_id\": \"$PROJECT_ID\", \"title\": \"Smoke Test Task\"}"

if [ "$HTTP_STATUS" = "201" ]; then
    TASK_ID=$(echo "$BODY" | jq -r '.id')
    pass_step "Created task $TASK_ID"
else
    fail_step "Create task" "Expected 201, got $HTTP_STATUS"
fi

# -----------------------------------------------------------------------
# Step 7: Log activity
# -----------------------------------------------------------------------
echo "Step 7: Log activity"
api_call POST /api/activity "{\"action_type\": \"completed\", \"notes\": \"Automated smoke test entry\"}"

if [ "$HTTP_STATUS" = "201" ]; then
    ACTIVITY_ID=$(echo "$BODY" | jq -r '.id')
    pass_step "Logged activity $ACTIVITY_ID"
else
    fail_step "Log activity" "Expected 201, got $HTTP_STATUS"
fi

# -----------------------------------------------------------------------
# Step 8: Get activity summary
# -----------------------------------------------------------------------
echo "Step 8: Activity summary"
TODAY=$(date -u +%Y-%m-%dT00:00:00)
TOMORROW=$(date -u -d "+1 day" +%Y-%m-%dT00:00:00 2>/dev/null || date -u -v+1d +%Y-%m-%dT00:00:00 2>/dev/null)

api_call GET "/api/reports/activity-summary?after=$TODAY&before=$TOMORROW"

if [ "$HTTP_STATUS" = "200" ]; then
    pass_step "Activity summary returned successfully"
else
    fail_step "Activity summary" "Expected 200, got $HTTP_STATUS"
fi

# -----------------------------------------------------------------------
# Step 9: Cleanup
# -----------------------------------------------------------------------
echo ""
echo "Step 9: Cleanup"

api_call DELETE "/api/activity/$ACTIVITY_ID"
if [ "$HTTP_STATUS" = "204" ]; then
    pass_step "Deleted activity"
    ACTIVITY_ID=""
else
    fail_step "Delete activity" "Expected 204, got $HTTP_STATUS"
fi

api_call DELETE "/api/tasks/$TASK_ID"
if [ "$HTTP_STATUS" = "204" ]; then
    pass_step "Deleted task"
    TASK_ID=""
else
    fail_step "Delete task" "Expected 204, got $HTTP_STATUS"
fi

api_call DELETE "/api/projects/$PROJECT_ID"
if [ "$HTTP_STATUS" = "204" ]; then
    pass_step "Deleted project"
    PROJECT_ID=""
else
    fail_step "Delete project" "Expected 204, got $HTTP_STATUS"
fi

api_call DELETE "/api/goals/$GOAL_ID"
if [ "$HTTP_STATUS" = "204" ]; then
    pass_step "Deleted goal"
    GOAL_ID=""
else
    fail_step "Delete goal" "Expected 204, got $HTTP_STATUS"
fi

api_call DELETE "/api/domains/$DOMAIN_ID"
if [ "$HTTP_STATUS" = "204" ]; then
    pass_step "Deleted domain"
    DOMAIN_ID=""
else
    fail_step "Delete domain" "Expected 204, got $HTTP_STATUS"
fi

# -----------------------------------------------------------------------
# Results
# -----------------------------------------------------------------------
echo ""
echo "============================================"
echo -e "  ${GREEN}All $PASSED tests passed.${NC}"
echo "============================================"
exit 0
