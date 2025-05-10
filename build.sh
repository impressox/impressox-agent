#!/bin/bash

# Get the project root directory
PROJECT_ROOT=$(git rev-parse --show-toplevel)

# Create a temporary directory for build context
TEMP_DIR=$(mktemp -d)

# Create necessary directories
mkdir -p "$TEMP_DIR/src"
mkdir -p "$TEMP_DIR/configs"

# Copy necessary files to temp directory
cp -r app/* "$TEMP_DIR/src/"
cp requirements.txt "$TEMP_DIR/"

# Build the Docker image
docker build -t hiepht/cpx:agent-api-$1 -f .dockers/Dockerfile.Prod "$TEMP_DIR"
docker push hiepht/cpx:agent-api-$1
docker rmi -f hiepht/cpx:agent-api-$1

# Clean up
rm -rf "$TEMP_DIR" 