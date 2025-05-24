#!/bin/bash

# Check if required environment variables are set
if [ -z "$DIAMOND_ADDRESS" ]; then
    echo "Error: DIAMOND_ADDRESS environment variable is required"
    exit 1
fi

# Function to display usage
show_usage() {
    echo "Usage:"
    echo "  ./test-deployed.sh"
    echo ""
    echo "Environment variables:"
    echo "  DIAMOND_ADDRESS - Address of the diamond contract"
    echo "  NETWORK        - Network to run tests on (default: localhost)"
}

# Check if help is requested
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    show_usage
    exit 0
fi

# Set network if provided
if [ ! -z "$NETWORK" ]; then
    NETWORK_ARG="--network $NETWORK"
else
    NETWORK_ARG="--network localhost"
fi

# Run the test script
echo "Testing deployed contract..."
echo "Diamond address: $DIAMOND_ADDRESS"
echo "Network: ${NETWORK_ARG#--network }"
echo ""

npx hardhat run scripts/test-deployed.js $NETWORK_ARG 