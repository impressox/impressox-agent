// SPDX-License-Identifier: MIT
pragma solidity 0.8.23;

import {IDiamondCut} from "../interfaces/IDiamondCut.sol";

contract RecursiveInit {
    IDiamondCut private immutable diamondCut;
    
    constructor() {
        diamondCut = IDiamondCut(msg.sender);
    }
    
    function initialize() external {
        // Try to make another diamondCut call during initialization
        // This should fail as we don't want recursive initialization
        IDiamondCut.FacetCut[] memory cut;
        diamondCut.diamondCut(cut, address(this), abi.encodeWithSignature("initialize()"));
    }
}
