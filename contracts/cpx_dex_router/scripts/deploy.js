/* global ethers */
/* eslint prefer-const: "off" */

const { getSelectors, FacetCutAction } = require('./libraries/diamond.js')
const { ethers } = require("hardhat");

// Aggregator addresses for different networks
const AGGREGATOR_ADDRESSES = {
  // Ethereum Mainnet
  1: {
    lifi: "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE",
    oneInch: "0x111111125421cA6dc452d289314280a0f8842A65"
  },
  // Polygon
  137: {
    lifi: "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE",
    oneInch: "0x111111125421cA6dc452d289314280a0f8842A65"
  },
  // BSC
  56: {
    lifi: "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE",
    oneInch: "0x111111125421cA6dc452d289314280a0f8842A65"
  },
  // Base
  8453: {
    lifi: "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE",
    oneInch: "0x111111125421cA6dc452d289314280a0f8842A65"
  }
}

// Facet configuration
const FACET_CONFIG = {
  // Core facets (no constructor params)
  core: [
    'DiamondLoupeFacet',
    'OwnershipFacet',
    'FeeCollectorFacet'
  ],
  // Aggregator facets (require constructor params)
  aggregator: {
    'LifiProxyFacet': (addresses) => [addresses.lifi],
    'OneInchProxyFacet': (addresses) => [addresses.oneInch]
  }
}

async function deployDiamond() {
    const [owner] = await ethers.getSigners();

    // Get network ID and aggregator addresses
    const networkId = (await ethers.provider.getNetwork()).chainId;
    const aggregatorAddresses = AGGREGATOR_ADDRESSES[networkId];
    if (!aggregatorAddresses) {
        throw new Error(`No aggregator addresses configured for network ${networkId}`);
    }

    console.log('Deploying core contracts...');
    
    // Deploy DiamondCutFacet
    const DiamondCutFacet = await ethers.getContractFactory("DiamondCutFacet");
    const diamondCutFacet = await DiamondCutFacet.deploy();
    await diamondCutFacet.waitForDeployment();
    console.log("DiamondCutFacet deployed:", await diamondCutFacet.getAddress());

    // Deploy DiamondInit
    const DiamondInit = await ethers.getContractFactory("DiamondInit");
    const diamondInit = await DiamondInit.deploy();
    await diamondInit.waitForDeployment();
    console.log("DiamondInit deployed:", await diamondInit.getAddress());

    // Deploy Diamond
    const Diamond = await ethers.getContractFactory("Diamond");
    const diamond = await Diamond.deploy(await owner.getAddress(), await diamondCutFacet.getAddress());
    await diamond.waitForDeployment();
    console.log("Diamond deployed:", await diamond.getAddress());

    console.log('\nDeploying facets...');
    const cut = [];

    // Deploy core facets
    for (const facetName of FACET_CONFIG.core) {
        const Facet = await ethers.getContractFactory(facetName);
        const facet = await Facet.deploy();
        await facet.waitForDeployment();
        console.log(`${facetName} deployed:`, await facet.getAddress());
        
        cut.push({
            facetAddress: await facet.getAddress(),
            action: FacetCutAction.Add,
            functionSelectors: getSelectors(facet)
        });
    }

    // Deploy aggregator facets
    for (const [facetName, getConstructorArgs] of Object.entries(FACET_CONFIG.aggregator)) {
        const constructorArgs = getConstructorArgs(aggregatorAddresses);
        const Facet = await ethers.getContractFactory(facetName);
        const facet = await Facet.deploy(...constructorArgs);
        await facet.waitForDeployment();
        console.log(`${facetName} deployed:`, await facet.getAddress());
        
        cut.push({
            facetAddress: await facet.getAddress(),
            action: FacetCutAction.Add,
            functionSelectors: getSelectors(facet)
        });
    }

    console.log('\nAdding facets to diamond...');
    const diamondCut = await ethers.getContractAt("IDiamondCut", await diamond.getAddress());
    
    // Encode init function call
    const initFunctionCall = diamondInit.interface.encodeFunctionData('init');
    
    // Add facets and initialize
    await diamondCut.diamondCut(cut, await diamondInit.getAddress(), initFunctionCall);
    console.log("Facets added to diamond and initialized");

    // Set fee recipient
    const feeCollector = await ethers.getContractAt("FeeCollectorFacet", await diamond.getAddress());
    await feeCollector.setFeeRecipient(process.env.FEE_RECIPIENT);
    console.log("Fee recipient set to:", process.env.FEE_RECIPIENT);

    return {
        diamond: await diamond.getAddress(),
        diamondCutFacet: await diamondCutFacet.getAddress(),
        diamondInit: await diamondInit.getAddress(),
        facets: cut.map(c => ({
            address: c.facetAddress,
            selectors: c.functionSelectors
        }))
    };
}

// We recommend this pattern to be able to use async/await everywhere
// and properly handle errors.
if (require.main === module) {
    deployDiamond()
        .then((addresses) => {
            console.log("\nDeployment addresses:", addresses);
            process.exit(0);
        })
        .catch((error) => {
            console.error(error);
            process.exit(1);
        });
}

exports.deployDiamond = deployDiamond