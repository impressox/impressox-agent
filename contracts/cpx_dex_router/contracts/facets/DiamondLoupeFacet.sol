// SPDX-License-Identifier: MIT
pragma solidity 0.8.23;

import {LibDiamond} from "../libraries/LibDiamond.sol";
import {IDiamondLoupe} from "../interfaces/IDiamondLoupe.sol";
import {IERC165} from "../interfaces/IERC165.sol";

contract DiamondLoupeFacet is IDiamondLoupe, IERC165 {
    // Returns all facets and their selectors
    function facets() external view override returns (Facet[] memory facets_) {
        LibDiamond.DiamondStorage storage ds = LibDiamond.diamondStorage();
        uint256 numFacets = ds.facetAddresses.length;
        facets_ = new Facet[](numFacets);

        for (uint256 i = 0; i < numFacets; i++) {
            address facetAddr = ds.facetAddresses[i];
            bytes4[] memory selectors = ds.facetFunctionSelectors[facetAddr].functionSelectors;
            facets_[i] = Facet({
                facetAddress: facetAddr,
                functionSelectors: selectors
            });
        }
    }

    // Returns all function selectors for a facet
    function facetFunctionSelectors(address _facet) external view override returns (bytes4[] memory selectors) {
        LibDiamond.DiamondStorage storage ds = LibDiamond.diamondStorage();
        return ds.facetFunctionSelectors[_facet].functionSelectors;
    }

    // Returns all facet addresses
    function facetAddresses() external view override returns (address[] memory addresses) {
        LibDiamond.DiamondStorage storage ds = LibDiamond.diamondStorage();
        return ds.facetAddresses;
    }

    // Returns facet address given selector
    function facetAddress(bytes4 _functionSelector) external view override returns (address facetAddr) {
        LibDiamond.DiamondStorage storage ds = LibDiamond.diamondStorage();
        facetAddr = ds.selectorToFacetAndPosition[_functionSelector].facetAddress;
    }

    // ERC-165 support
    function supportsInterface(bytes4 _interfaceId) external view override returns (bool) {
        LibDiamond.DiamondStorage storage ds = LibDiamond.diamondStorage();
        return ds.supportedInterfaces[_interfaceId];
    }
}