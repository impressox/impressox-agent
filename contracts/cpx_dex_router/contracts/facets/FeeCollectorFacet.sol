// SPDX-License-Identifier: MIT
pragma solidity 0.8.23;

import {LibFeeCollector} from "../libraries/LibFeeCollector.sol";
import {LibDiamond} from "../libraries/LibDiamond.sol";

contract FeeCollectorFacet {
    function setFeeRecipient(address _recipient) external {
        LibDiamond.enforceIsContractOwner();
        LibFeeCollector.setRecipient(_recipient);
    }

    function getFeeRecipient() external view returns (address) {
        return LibFeeCollector.getRecipient();
    }
} 