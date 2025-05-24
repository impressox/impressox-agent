// SPDX-License-Identifier: MIT
pragma solidity 0.8.23;

contract MockAggregator {
    bool public shouldFail;

    function setShouldFail(bool _shouldFail) external {
        shouldFail = _shouldFail;
    }

    function swap(
        address fromToken,
        uint256 fromAmount,
        address toToken,
        uint256 minToAmount
    ) external payable returns (uint256) {
        if (shouldFail) {
            revert("Mock aggregator failure");
        }
        return minToAmount;
    }
} 