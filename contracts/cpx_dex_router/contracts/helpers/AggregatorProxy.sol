// SPDX-License-Identifier: MIT
pragma solidity 0.8.23;

import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ReentrancyGuard} from "./ReentrancyGuard.sol";
import {RouterErrors} from "../errors/RouterErrors.sol";
import {LibFeeCollector} from "../libraries/LibFeeCollector.sol";

contract AggregatorProxy is ReentrancyGuard {
    using SafeERC20 for IERC20;

    uint256 private constant FEE_PERCENTAGE_BASE = 10000;
    address private immutable aggregator;
    
    event FeeCollected(address indexed token, address indexed recipient, uint256 amount);
    event TokensTransferred(address indexed token, address indexed to, uint256 amount);
    
    error InvalidAggregator();
    error InvalidFeePercentage(uint16 fee);
    error TransferFailed();

    constructor(address _aggregator) {
        if (_aggregator == address(0) || _aggregator.code.length <= 100) {
            revert InvalidAggregator();
        }
        aggregator = _aggregator;
    }

    function _parseAddressAndFee(uint256 tokenWithFee) 
        internal 
        pure 
        returns (address token, uint16 fee) 
    {
        token = address(uint160(tokenWithFee));
        fee = uint16(tokenWithFee >> 160);
        if (fee >= FEE_PERCENTAGE_BASE) {
            revert InvalidFeePercentage(fee);
        }
    }

    function _handleTokenTransfer(
        address token,
        address recipient, 
        uint256 amount
    ) internal returns (bool) {
        if (amount == 0) return true;
        
        if (token == address(0)) {
            (bool success,) = recipient.call{value: amount}("");
            if (success) {
                emit TokensTransferred(token, recipient, amount);
            }
            return success;
        }
        
        try IERC20(token).safeTransfer(recipient, amount) {
            emit TokensTransferred(token, recipient, amount);
            return true;
        } catch {
            return false;
        }
    }

    function _processFees(
        address token,
        uint256 amount,
        uint16 fee,
        bool isInput
    ) internal returns (uint256 remainingAmount) {
        if (fee == 0) return amount;
        
        address feeRecipient = LibFeeCollector.getRecipient();
        uint256 feeAmount = (amount * fee) / FEE_PERCENTAGE_BASE;
        remainingAmount = amount - feeAmount;
        
        if (isInput) {
            if (token != address(0)) {
                IERC20(token).safeTransferFrom(msg.sender, feeRecipient, feeAmount);
            } else {
                if (!_handleTokenTransfer(token, feeRecipient, feeAmount)) {
                    revert TransferFailed();
                }
            }
        } else {
            if (!_handleTokenTransfer(token, feeRecipient, feeAmount)) {
                revert TransferFailed();
            }
        }
        
        emit FeeCollected(token, feeRecipient, feeAmount);
        return remainingAmount;
    }

    function _callAggregator(
        uint256 fromTokenWithFee,
        uint256 fromAmount,
        uint256 toTokenWithFee,
        bytes calldata callData
    ) internal nonReentrant {
        // Cache initial balances
        uint256 initialEthBalance = address(this).balance - msg.value;
        
        // Parse token information
        (address fromToken, uint16 fromFee) = _parseAddressAndFee(fromTokenWithFee);
        (address toToken, uint16 toFee) = _parseAddressAndFee(toTokenWithFee);
        
        // Process input tokens and fees
        uint256 processedAmount = fromAmount;
        uint256 msgValue = msg.value;
        
        if (fromToken == address(0)) {
            if (fromFee > 0) {
                msgValue = _processFees(fromToken, fromAmount, fromFee, true);
            }
        } else {
            if (fromFee > 0) {
                processedAmount = _processFees(fromToken, fromAmount, fromFee, true);
            }
            
            IERC20(fromToken).safeTransferFrom(msg.sender, address(this), processedAmount);
            if (!_makeCall(IERC20(fromToken), IERC20.approve.selector, aggregator, processedAmount)) {
                revert RouterErrors.ApproveFailed();
            }
        }

        // Call aggregator
        (bool success, bytes memory result) = aggregator.call{value: msgValue}(callData);
        if (!success) {
            assembly {
                revert(add(result, 32), mload(result))
            }
        }

        // Reset approvals and handle remaining balances
        if (fromToken != address(0)) {
            if (!_makeCall(IERC20(fromToken), IERC20.approve.selector, aggregator, 0)) {
                revert RouterErrors.ApproveFailed();
            }
            
            uint256 remainingBalance = IERC20(fromToken).balanceOf(address(this));
            if (remainingBalance > 0) {
                _handleTokenTransfer(fromToken, msg.sender, remainingBalance);
            }
        }

        // Process output tokens
        uint256 outputBalance;
        if (toToken == address(0)) {
            outputBalance = address(this).balance - initialEthBalance;
        } else {
            outputBalance = IERC20(toToken).balanceOf(address(this));
        }

        if (outputBalance > 0) {
            uint256 finalAmount = toFee > 0 
                ? _processFees(toToken, outputBalance, toFee, false)
                : outputBalance;
                
            if (!_handleTokenTransfer(toToken, msg.sender, finalAmount)) {
                revert TransferFailed();
            }
        }
    }

    function _makeCall(
        IERC20 token,
        bytes4 selector,
        address to,
        uint256 amount
    ) private returns (bool success) {
        assembly ("memory-safe") {
            let data := mload(0x40)
            mstore(data, selector)
            mstore(add(data, 0x04), to)
            mstore(add(data, 0x24), amount)
            success := call(gas(), token, 0, data, 0x44, 0x0, 0x20)
            if success {
                switch returndatasize()
                case 0 { success := gt(extcodesize(token), 0) }
                default { success := and(gt(returndatasize(), 31), eq(mload(0), 1)) }
            }
        }
    }
}