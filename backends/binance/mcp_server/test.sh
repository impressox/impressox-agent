#!/bin/bash

# Exit on error
set -e

# Export test environment variables
export PYTHONPATH=${PYTHONPATH:+$PYTHONPATH:}$(pwd)
export MCP_ENV=test

# Clean up previous test artifacts
echo "Cleaning up test artifacts..."
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
rm -rf .coverage htmlcov || true

# Install test dependencies if needed
if [ "$1" == "--install" ]; then
    echo "Installing test dependencies..."
    pip install -r requirements.txt
    shift
fi

# Run tests
echo "Running tests..."
if [ $# -eq 0 ]; then
    # Run all tests by default
    python -m pytest
else
    # Run specific tests if arguments provided
    python -m pytest "$@"
fi

# Generate coverage report
echo "Generating coverage report..."
coverage report
coverage html

echo "Tests completed!"
