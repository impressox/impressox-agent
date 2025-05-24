const { getSelectors, FacetCutAction } = require('./libraries/diamond.js')
const { ethers } = require("hardhat");

async function deployFacet(name, args = []) {
    const Facet = await ethers.getContractFactory(name);
    const facet = await Facet.deploy(...args);
    await facet.waitForDeployment();
    console.log(`${name} deployed:`, await facet.getAddress());
    return facet;
}

async function addFacet(diamondAddress, facetName, constructorArgs = []) {
    const [owner] = await ethers.getSigners();
    const diamondCut = await ethers.getContractAt("IDiamondCut", diamondAddress);

    // Deploy new facet
    const facet = await deployFacet(facetName, constructorArgs);

    // Prepare cut
    const cut = [{
        facetAddress: await facet.getAddress(),
        action: FacetCutAction.Add,
        functionSelectors: getSelectors(facet)
    }];

    // Add facet to diamond
    await diamondCut.diamondCut(cut, ethers.ZeroAddress, "0x");
    console.log(`Added ${facetName} to diamond`);

    return facet;
}

async function replaceFacet(diamondAddress, facetName, constructorArgs = []) {
    const [owner] = await ethers.getSigners();
    const diamondCut = await ethers.getContractAt("IDiamondCut", diamondAddress);

    // Deploy new facet
    const facet = await deployFacet(facetName, constructorArgs);

    // Prepare cut
    const cut = [{
        facetAddress: await facet.getAddress(),
        action: FacetCutAction.Replace,
        functionSelectors: getSelectors(facet)
    }];

    // Replace facet in diamond
    await diamondCut.diamondCut(cut, ethers.ZeroAddress, "0x");
    console.log(`Replaced ${facetName} in diamond`);

    return facet;
}

async function removeFacet(diamondAddress, facetName) {
    const [owner] = await ethers.getSigners();
    const diamondCut = await ethers.getContractAt("IDiamondCut", diamondAddress);

    // Get facet interface to get function selectors
    const Facet = await ethers.getContractFactory(facetName);
    const facet = await Facet.deploy();
    await facet.waitForDeployment();

    // Prepare cut
    const cut = [{
        facetAddress: ethers.ZeroAddress,
        action: FacetCutAction.Remove,
        functionSelectors: getSelectors(facet)
    }];

    // Remove facet from diamond
    await diamondCut.diamondCut(cut, ethers.ZeroAddress, "0x");
    console.log(`Removed ${facetName} from diamond`);
}

async function main() {
    const diamondAddress = process.env.DIAMOND_ADDRESS;
    if (!diamondAddress) {
        throw new Error("DIAMOND_ADDRESS environment variable is required");
    }

    const action = process.env.ACTION;
    const facetName = process.env.FACET_NAME;

    if (!action || !facetName) {
        throw new Error("ACTION and FACET_NAME environment variables are required");
    }

    // Parse constructor arguments from environment variable
    let constructorArgs = [];
    if (process.env.CONSTRUCTOR_ARGS) {
        try {
            constructorArgs = JSON.parse(process.env.CONSTRUCTOR_ARGS);
            if (!Array.isArray(constructorArgs)) {
                throw new Error("CONSTRUCTOR_ARGS must be a JSON array");
            }
        } catch (e) {
            throw new Error(`Invalid CONSTRUCTOR_ARGS: ${e.message}`);
        }
    }

    switch (action.toLowerCase()) {
        case 'add':
            await addFacet(diamondAddress, facetName, constructorArgs);
            break;
        case 'replace':
            await replaceFacet(diamondAddress, facetName, constructorArgs);
            break;
        case 'remove':
            await removeFacet(diamondAddress, facetName);
            break;
        default:
            throw new Error(`Invalid action: ${action}. Must be one of: add, replace, remove`);
    }
}

if (require.main === module) {
    main()
        .then(() => process.exit(0))
        .catch((error) => {
            console.error(error);
            process.exit(1);
        });
}

exports.addFacet = addFacet;
exports.replaceFacet = replaceFacet;
exports.removeFacet = removeFacet; 