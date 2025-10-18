#!/bin/bash
# Self-contained test runner with virtual environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_VENV="$SCRIPT_DIR/.test-venv"

# Create test virtual environment if it doesn't exist
if [ ! -d "$TEST_VENV" ]; then
    echo "Creating test virtual environment..."
    python3 -m venv "$TEST_VENV"
    echo "Installing test dependencies..."
    "$TEST_VENV/bin/pip" install -q --upgrade pip
    "$TEST_VENV/bin/pip" install -q -r "$SCRIPT_DIR/test-requirements.txt"
fi

# Run tests using the test venv
echo "Running tests..."
"$TEST_VENV/bin/pytest" "$@" "$SCRIPT_DIR/tests"
