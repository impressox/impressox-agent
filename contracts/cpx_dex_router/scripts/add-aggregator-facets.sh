#!/bin/bash

# Check if required environment variables are set
if [ -z "$DIAMOND_ADDRESS" ]; then
    echo "Error: DIAMOND_ADDRESS environment variable is required"
    exit 1
fi

# Network IDs and their aggregator addresses
declare -A LIFI_ADDRESSES=(
    ["1"]="0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE"    # Ethereum Mainnet
    ["137"]="0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE"  # Polygon
    ["56"]="0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE"   # BSC
    ["8453"]="0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE" # Base
)

declare -A ONEINCH_ADDRESSES=(
    ["1"]="0x111111125421cA6dc452d289314280a0f8842A65"    # Ethereum Mainnet
    ["137"]="0x111111125421cA6dc452d289314280a0f8842A65"  # Polygon
    ["56"]="0x111111125421cA6dc452d289314280a0f8842A65"   # BSC
    ["8453"]="0x111111125421cA6dc452d289314280a0f8842A65" # Base
)

# Function to display usage
show_usage() {
    echo "Usage:"
    echo "  ./add-aggregator-facets.sh <network_id>"
    echo ""
    echo "Network IDs:"
    echo "  1    - Ethereum Mainnet"
    echo "  137  - Polygon"
    echo "  56   - BSC"
    echo "  8453 - Base"
    echo ""
    echo "Environment variables:"
    echo "  DIAMOND_ADDRESS - Address of the diamond contract"
}

# Check if help is requested
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    show_usage
    exit 0
fi

# Check if network ID is provided
if [ -z "$1" ]; then
    echo "Error: Network ID is required"
    show_usage
    exit 1
fi

NETWORK_ID=$1

# Check if network ID is valid
if [ -z "${LIFI_ADDRESSES[$NETWORK_ID]}" ]; then
    echo "Error: Invalid network ID"
    show_usage
    exit 1
fi

# Add LifiProxyFacet
echo "Adding LifiProxyFacet..."
export ACTION="add"
export FACET_NAME="LifiProxyFacet"
export CONSTRUCTOR_ARGS="[\"${LIFI_ADDRESSES[$NETWORK_ID]}\"]"
npx hardhat run scripts/manageFacets.js

# Add OneInchProxyFacet
echo "Adding OneInchProxyFacet..."
export ACTION="add"
export FACET_NAME="OneInchProxyFacet"
export CONSTRUCTOR_ARGS="[\"${ONEINCH_ADDRESSES[$NETWORK_ID]}\"]"
npx hardhat run scripts/manageFacets.js

echo "Done!" 