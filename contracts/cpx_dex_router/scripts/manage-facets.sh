#!/bin/bash

# Check if required environment variables are set
if [ -z "$DIAMOND_ADDRESS" ]; then
    echo "Error: DIAMOND_ADDRESS environment variable is required"
    exit 1
fi

if [ -z "$ACTION" ]; then
    echo "Error: ACTION environment variable is required (add/replace/remove)"
    exit 1
fi

if [ -z "$FACET_NAME" ]; then
    echo "Error: FACET_NAME environment variable is required"
    exit 1
fi

# Function to display usage
show_usage() {
    echo "Usage:"
    echo "  ./manage-facets.sh <action> <facet_name> [constructor_args]"
    echo ""
    echo "Actions:"
    echo "  add     - Add a new facet to the diamond"
    echo "  replace - Replace an existing facet in the diamond"
    echo "  remove  - Remove a facet from the diamond"
    echo ""
    echo "Examples:"
    echo "  ./manage-facets.sh add NewFacet '[\"0x123\"]'"
    echo "  ./manage-facets.sh replace NewFacet '[\"0x123\", 100]'"
    echo "  ./manage-facets.sh remove NewFacet"
    echo ""
    echo "Environment variables:"
    echo "  DIAMOND_ADDRESS - Address of the diamond contract"
    echo "  ACTION          - Action to perform (add/replace/remove)"
    echo "  FACET_NAME      - Name of the facet to manage"
    echo "  CONSTRUCTOR_ARGS - Constructor arguments as JSON array (optional)"
}

# Check if help is requested
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    show_usage
    exit 0
fi

# Set environment variables from command line arguments
export DIAMOND_ADDRESS="$DIAMOND_ADDRESS"
export ACTION="$ACTION"
export FACET_NAME="$FACET_NAME"

# Set constructor arguments if provided
if [ ! -z "$CONSTRUCTOR_ARGS" ]; then
    export CONSTRUCTOR_ARGS="$CONSTRUCTOR_ARGS"
fi

# Run the script
echo "Managing facets..."
echo "Diamond address: $DIAMOND_ADDRESS"
echo "Action: $ACTION"
echo "Facet name: $FACET_NAME"
if [ ! -z "$CONSTRUCTOR_ARGS" ]; then
    echo "Constructor args: $CONSTRUCTOR_ARGS"
fi
echo ""

npx hardhat run scripts/manageFacets.js 