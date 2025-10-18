#!/bin/bash
# End-to-end integration test for worktree manager
# Tests creation, setup, and deletion using your actual repository configuration

set -e

# Ensure cleanup runs even on errors
set -E
trap 'cleanup_on_error' ERR

# Colors for output
RED='\033[91m'
GREEN='\033[92m'
BLUE='\033[94m'
YELLOW='\033[93m'
BOLD='\033[1m'
END='\033[0m'

# Test configuration
TEST_WORKTREE_NAME="e2e-test-wt"
REPO_ALIAS="${1}"  # Repository alias from command line

# Usage function
usage() {
    echo -e "${BOLD}Usage:${END} $0 <repo-alias>"
    echo ""
    echo "Run end-to-end integration test using your actual repository."
    echo ""
    echo "Example:"
    echo "  $0 onyx"
    echo ""
    echo "Available repositories:"
    worktree repo list 2>/dev/null || echo "  (none configured)"
    exit 1
}

# Check for repo alias argument
if [ -z "$REPO_ALIAS" ]; then
    echo -e "${RED}Error: Repository alias required${END}\n"
    usage
fi

# Verify repository exists (strip ANSI colors for grep)
REPO_LIST=$(worktree repo list 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g')
if ! echo "$REPO_LIST" | grep -q "✓.*$REPO_ALIAS"; then
    echo -e "${RED}Error: Repository alias '$REPO_ALIAS' not found${END}\n"
    echo "Available repositories:"
    worktree repo list
    exit 1
fi

# Cleanup function
cleanup() {
    local exit_code=$?
    echo -e "\n${BLUE}==>${END} ${BOLD}Cleaning up test worktree...${END}"

    # Remove worktree if it exists
    if worktree "$REPO_ALIAS" list 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | grep -q "✓.*$TEST_WORKTREE_NAME"; then
        echo "  Removing test worktree..."
        worktree "$REPO_ALIAS" rm "$TEST_WORKTREE_NAME" --force 2>/dev/null || true
    fi

    # Remove git branch if it still exists
    cd "$REPO_PATH" 2>/dev/null || true
    if git branch 2>/dev/null | grep -q "$TEST_WORKTREE_NAME"; then
        echo "  Removing git branch..."
        git branch -D "$TEST_WORKTREE_NAME" 2>/dev/null || true
    fi

    echo -e "${GREEN}✓${END} Cleanup complete"
    exit $exit_code
}

# Cleanup on error
cleanup_on_error() {
    echo -e "\n${RED}Test failed with error${END}"
    cleanup
}

# Set up trap for cleanup
trap cleanup EXIT

# Print header
echo -e "${BOLD}================================${END}"
echo -e "${BOLD}Worktree Manager E2E Test${END}"
echo -e "${BOLD}Repository: $REPO_ALIAS${END}"
echo -e "${BOLD}================================${END}\n"

# Step 1: Verify repository configuration
echo -e "${BLUE}==>${END} ${BOLD}Step 1: Verifying repository configuration${END}"

# Get repo path (strip ANSI colors and parse)
REPO_LIST_RAW=$(worktree repo list 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g')
REPO_PATH=$(echo "$REPO_LIST_RAW" | grep -A1 "✓.*$REPO_ALIAS" | tail -1 | xargs)

if [ ! -d "$REPO_PATH" ]; then
    echo -e "${RED}✗${END} Repository path does not exist: $REPO_PATH"
    exit 1
fi

echo -e "${GREEN}✓${END} Repository configured: $REPO_PATH"

# Check for setup configuration
SETUP_CONFIG=""
HAS_USER_SETUP=false
for config in "$REPO_PATH/${REPO_ALIAS}-setup.yaml" "$REPO_PATH/${REPO_ALIAS}-setup.yml" "$REPO_PATH/${REPO_ALIAS}-setup.json" "$REPO_PATH/.worktree-setup.yaml" "$REPO_PATH/.worktree-setup.yml" "$REPO_PATH/.worktree-setup.json"; do
    if [ -f "$config" ]; then
        SETUP_CONFIG="$config"
        HAS_USER_SETUP=true
        echo -e "${GREEN}✓${END} Setup configuration found: $(basename $SETUP_CONFIG)"
        break
    fi
done

if [ -z "$SETUP_CONFIG" ]; then
    echo -e "${YELLOW}⚠${END} No setup configuration found"
    echo -e "${YELLOW}  The test will create a worktree but won't run setup steps${END}"
fi

echo ""

# Step 2: Check for existing test worktree
echo -e "${BLUE}==>${END} ${BOLD}Step 2: Checking for existing test worktree${END}"

if worktree "$REPO_ALIAS" list 2>/dev/null | grep -q "$TEST_WORKTREE_NAME"; then
    echo -e "${YELLOW}⚠${END} Test worktree already exists, removing it first..."
    worktree "$REPO_ALIAS" rm "$TEST_WORKTREE_NAME" --force
fi

echo -e "${GREEN}✓${END} Ready to create test worktree\n"

# Step 3: Create worktree
echo -e "${BLUE}==>${END} ${BOLD}Step 3: Creating test worktree${END}"

# Get main branch name
cd "$REPO_PATH"
MAIN_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")

worktree "$REPO_ALIAS" new "$TEST_WORKTREE_NAME" --base "$MAIN_BRANCH"

# Find worktree path by parsing the multi-line output
WORKTREE_PATH=$(worktree "$REPO_ALIAS" list | sed 's/\x1b\[[0-9;]*m//g' | grep -A2 "✓.*$TEST_WORKTREE_NAME" | grep "Path:" | awk '{print $2}')

if [ ! -d "$WORKTREE_PATH" ]; then
    echo -e "${RED}✗${END} Worktree directory not created"
    exit 1
fi

echo -e "${GREEN}✓${END} Worktree created: $WORKTREE_PATH\n"

# Step 4: Verify worktree setup
echo -e "${BLUE}==>${END} ${BOLD}Step 4: Verifying worktree${END}"

cd "$WORKTREE_PATH"

FAILED_CHECKS=0

# Check 1: Git branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "$TEST_WORKTREE_NAME" ]; then
    echo -e "${GREEN}✓${END} Git branch created: $CURRENT_BRANCH"
else
    echo -e "${RED}✗${END} Git branch incorrect (expected: $TEST_WORKTREE_NAME, got: $CURRENT_BRANCH)"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

# Check 2: Working directory is clean (worktrees have .git file, not directory)
if [ -f ".git" ] || [ -d ".git" ]; then
    echo -e "${GREEN}✓${END} Git working directory initialized"
else
    echo -e "${RED}✗${END} Git working directory not properly initialized"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

# Check 3: Verify setup execution (if config exists)
if [ -n "$SETUP_CONFIG" ]; then
    echo -e "\n${BOLD}Checking setup execution:${END}"

    # Look for common setup artifacts
    SETUP_ARTIFACTS=0

    if [ -d ".venv" ] || [ -d "venv" ]; then
        echo -e "${GREEN}✓${END} Virtual environment created"
        SETUP_ARTIFACTS=$((SETUP_ARTIFACTS + 1))
    fi

    if [ -d "node_modules" ]; then
        echo -e "${GREEN}✓${END} Node modules installed"
        SETUP_ARTIFACTS=$((SETUP_ARTIFACTS + 1))
    fi

    if [ -f ".env" ] || [ -f ".vscode/.env" ]; then
        echo -e "${GREEN}✓${END} Environment file created"
        SETUP_ARTIFACTS=$((SETUP_ARTIFACTS + 1))
    fi

    if [ -d "backend" ] && [ -d ".venv" ]; then
        # Check if backend packages were installed (look for site-packages)
        if [ -d ".venv/lib/python"*/site-packages/* ] 2>/dev/null; then
            echo -e "${GREEN}✓${END} Backend dependencies installed"
            SETUP_ARTIFACTS=$((SETUP_ARTIFACTS + 1))
        fi
    fi

    # Check for any newly created directories/files (compared to main repo)
    NEW_ITEMS=$(comm -13 <(cd "$REPO_PATH" && ls -A 2>/dev/null | sort) <(ls -A 2>/dev/null | sort) 2>/dev/null | wc -l | tr -d ' ')
    if [ "$NEW_ITEMS" -gt 0 ]; then
        echo -e "${GREEN}✓${END} Setup created $NEW_ITEMS new items"
        SETUP_ARTIFACTS=$((SETUP_ARTIFACTS + 1))
    fi

    if [ $SETUP_ARTIFACTS -eq 0 ]; then
        echo -e "${YELLOW}⚠${END} No obvious setup artifacts detected (setup may have run but not created visible files)"
    else
        echo -e "${GREEN}✓${END} Setup ran successfully ($SETUP_ARTIFACTS artifacts found)"
    fi
fi

echo ""

# Step 5: List worktrees
echo -e "${BLUE}==>${END} ${BOLD}Step 5: Listing all worktrees${END}"

worktree "$REPO_ALIAS" list

echo ""

# Step 6: Test worktree operations
echo -e "${BLUE}==>${END} ${BOLD}Step 6: Testing worktree operations${END}"

# Test creating a file in the worktree
echo "# E2E Test" > e2e-test-file.txt
if [ -f "e2e-test-file.txt" ]; then
    echo -e "${GREEN}✓${END} File creation works"
else
    echo -e "${RED}✗${END} File creation failed"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

# Test git operations
git add e2e-test-file.txt 2>/dev/null
if git diff --cached --name-only | grep -q "e2e-test-file.txt"; then
    echo -e "${GREEN}✓${END} Git staging works"
else
    echo -e "${RED}✗${END} Git staging failed"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

# Reset the test file
git reset HEAD e2e-test-file.txt 2>/dev/null
rm e2e-test-file.txt

echo ""

# Step 7: Delete worktree
echo -e "${BLUE}==>${END} ${BOLD}Step 7: Deleting test worktree${END}"

worktree "$REPO_ALIAS" rm "$TEST_WORKTREE_NAME" --force

if [ -d "$WORKTREE_PATH" ]; then
    echo -e "${RED}✗${END} Worktree directory still exists after deletion"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
else
    echo -e "${GREEN}✓${END} Worktree deleted successfully"
fi

# Check branch was deleted
cd "$REPO_PATH"
if git branch | grep -q "$TEST_WORKTREE_NAME"; then
    echo -e "${RED}✗${END} Git branch still exists after deletion"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
else
    echo -e "${GREEN}✓${END} Git branch deleted successfully"
fi

echo ""

# Final results
echo -e "${BOLD}================================${END}"
echo -e "${BOLD}Test Results${END}"
echo -e "${BOLD}================================${END}\n"

if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ ALL TESTS PASSED${END}"
    echo -e "\nThe worktree manager is working correctly with repository '$REPO_ALIAS'!"
    echo -e "\nYou can now use it with confidence:"
    echo -e "  • Create worktrees: ${BOLD}worktree $REPO_ALIAS new <name>${END}"
    echo -e "  • List worktrees: ${BOLD}worktree $REPO_ALIAS list${END}"
    echo -e "  • Switch worktrees: ${BOLD}worktree $REPO_ALIAS select <name>${END}"
    echo -e "  • Remove worktrees: ${BOLD}worktree $REPO_ALIAS rm <name>${END}"
    exit 0
else
    echo -e "${RED}${BOLD}✗ $FAILED_CHECKS TESTS FAILED${END}"
    echo -e "\nSome checks did not pass. Please review the output above."
    exit 1
fi
