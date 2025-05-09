#!/bin/bash

# Get the project root directory
PROJECT_ROOT=$(git rev-parse --show-toplevel)

# Create a temporary directory for build context
TEMP_DIR=$(mktemp -d)

# Copy necessary files to temp directory
cp -r . "$TEMP_DIR/clients/telegram"
cp "$PROJECT_ROOT/clients/config.py" "$TEMP_DIR/clients/"
cp "$PROJECT_ROOT/clients/session_manager.py" "$TEMP_DIR/clients/"

# Build the Docker image
docker build -t hiepht/cpx:telegram-client-$1 -f Dockerfile "$TEMP_DIR"
docker push hiepht/cpx:telegram-client-$1
docker rm -f hiepht/cpx:telegram-client-$1
# Clean up
rm -rf "$TEMP_DIR" 