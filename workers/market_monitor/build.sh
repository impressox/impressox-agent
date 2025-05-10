#!/bin/bash

# Create a temporary directory for build context
TEMP_DIR=$(mktemp -d)

# Copy only the market_monitor directory to temp directory
cp -r . "$TEMP_DIR/"

# Build the Docker image
docker build -t hiepht/cpx:market-monitor-$1 -f Dockerfile "$TEMP_DIR"
docker push hiepht/cpx:market-monitor-$1
docker rmi -f hiepht/cpx:market-monitor-$1

# Clean up
rm -rf "$TEMP_DIR" 