const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("LifiProxyFacet", function () {
    let diamond;
    let lifiProxyFacet;
    let feeCollectorFacet;
    let mockAggregator;
    let mockToken;
    let owner;
    let user;
    let feeRecipient;

    beforeEach(async function () {
        [owner, user, feeRecipient] = await ethers.getSigners();

        // Deploy mock aggregator
        const MockAggregator = await ethers.getContractFactory("MockAggregator");
        mockAggregator = await MockAggregator.deploy();

        // Deploy mock token
        const MockToken = await ethers.getContractFactory("MockERC20");
        mockToken = await MockToken.deploy("Mock Token", "MTK");

        // Deploy DiamondCutFacet
        const DiamondCutFacet = await ethers.getContractFactory("DiamondCutFacet");
        const diamondCutFacet = await DiamondCutFacet.deploy();

        // Deploy Diamond
        const Diamond = await ethers.getContractFactory("Diamond");
        diamond = await Diamond.deploy(await owner.getAddress(), await diamondCutFacet.getAddress());

        // Deploy LifiProxyFacet
        const LifiProxyFacet = await ethers.getContractFactory("LifiProxyFacet");
        lifiProxyFacet = await LifiProxyFacet.deploy(await mockAggregator.getAddress());

        // Deploy FeeCollectorFacet
        const FeeCollectorFacet = await ethers.getContractFactory("FeeCollectorFacet");
        feeCollectorFacet = await FeeCollectorFacet.deploy();

        // Add facets to diamond
        const diamondCut = await ethers.getContractAt("IDiamondCut", await diamond.getAddress());
        const cut = [
            {
                facetAddress: await lifiProxyFacet.getAddress(),
                action: 0, // Add
                functionSelectors: [
                    lifiProxyFacet.interface.getFunction("callLifi").selector
                ]
            },
            {
                facetAddress: await feeCollectorFacet.getAddress(),
                action: 0, // Add
                functionSelectors: [
                    feeCollectorFacet.interface.getFunction("setFeeRecipient").selector,
                    feeCollectorFacet.interface.getFunction("getFeeRecipient").selector
                ]
            }
        ];

        await diamondCut.diamondCut(cut, ethers.ZeroAddress, "0x");

        // Set fee recipient
        const feeCollector = await ethers.getContractAt("FeeCollectorFacet", await diamond.getAddress());
        await feeCollector.setFeeRecipient(await feeRecipient.getAddress());
    });

    describe("Constructor", function () {
        it("Should revert if aggregator address is zero", async function () {
            const LifiProxyFacet = await ethers.getContractFactory("LifiProxyFacet");
            await expect(
                LifiProxyFacet.deploy(ethers.ZeroAddress)
            ).to.be.revertedWithCustomError(LifiProxyFacet, "InvalidAggregator");
        });
    });

    describe("Lifi Calls", function () {
        it("Should make Lifi calls correctly", async function () {
            const fromToken = await mockToken.getAddress();
            const toToken = await mockToken.getAddress();
            const amount = ethers.parseEther("1.0");
            const fromFee = 100; // 1%
            const toFee = 100; // 1%

            // Pack token address and fee into a single uint256
            const fromTokenWithFee = (BigInt(fromToken) | (BigInt(fromFee) << 160n));
            const toTokenWithFee = (BigInt(toToken) | (BigInt(toFee) << 160n));

            // Mint and approve tokens
            await mockToken.mint(await user.getAddress(), amount);
            await mockToken.connect(user).approve(await diamond.getAddress(), amount);

            // Create callData for swap function
            const callData = mockAggregator.interface.encodeFunctionData("swap", [
                fromToken,
                amount,
                toToken,
                amount
            ]);

            // Mint tokens to aggregator to simulate successful swap
            await mockToken.mint(await mockAggregator.getAddress(), amount);

            const lifiProxy = await ethers.getContractAt("LifiProxyFacet", await diamond.getAddress());
            await expect(
                lifiProxy.connect(user).callLifi(
                    fromTokenWithFee,
                    amount,
                    toTokenWithFee,
                    callData
                )
            ).to.not.be.reverted;
        });

        it("Should handle failed Lifi calls", async function () {
            const fromToken = await mockToken.getAddress();
            const toToken = await mockToken.getAddress();
            const amount = ethers.parseEther("1.0");
            const fromFee = 100; // 1%
            const toFee = 100; // 1%

            // Pack token address and fee into a single uint256
            const fromTokenWithFee = (BigInt(fromToken) | (BigInt(fromFee) << 160n));
            const toTokenWithFee = (BigInt(toToken) | (BigInt(toFee) << 160n));

            await mockToken.mint(await user.getAddress(), amount);
            await mockToken.connect(user).approve(await diamond.getAddress(), amount);

            // Set mock aggregator to fail
            await mockAggregator.setShouldFail(true);

            // Create callData for swap function
            const callData = mockAggregator.interface.encodeFunctionData("swap", [
                fromToken,
                amount,
                toToken,
                amount
            ]);

            const lifiProxy = await ethers.getContractAt("LifiProxyFacet", await diamond.getAddress());
            await expect(
                lifiProxy.connect(user).callLifi(
                    fromTokenWithFee,
                    amount,
                    toTokenWithFee,
                    callData
                )
            ).to.be.reverted;
        });

        it("Should handle ETH transfers correctly", async function () {
            const fromToken = ethers.ZeroAddress; // ETH
            const toToken = await mockToken.getAddress();
            const amount = ethers.parseEther("1.0");
            const fromFee = 100; // 1%
            const toFee = 100; // 1%

            // Pack token address and fee into a single uint256
            const fromTokenWithFee = (BigInt(fromToken) | (BigInt(fromFee) << 160n));
            const toTokenWithFee = (BigInt(toToken) | (BigInt(toFee) << 160n));

            // Create callData for swap function
            const callData = mockAggregator.interface.encodeFunctionData("swap", [
                fromToken,
                amount,
                toToken,
                amount
            ]);

            // Mint tokens to aggregator to simulate successful swap
            await mockToken.mint(await mockAggregator.getAddress(), amount);

            const lifiProxy = await ethers.getContractAt("LifiProxyFacet", await diamond.getAddress());
            await expect(
                lifiProxy.connect(user).callLifi(
                    fromTokenWithFee,
                    amount,
                    toTokenWithFee,
                    callData,
                    { value: amount }
                )
            ).to.not.be.reverted;
        });
    });
}); 