const { expect } = require("chai");
const { ethers } = require("hardhat");
const {
  getSelectors,
  FacetCutAction,
} = require("../scripts/libraries/diamond.js");

describe("Storage Upgrade Tests", function () {
  let diamondAddress;
  let diamondCutFacet;
  let complexStorageV3;
  let complexStorageV4;
  let owner;
  let addr1;
  let addr2;

  before(async function () {
    [owner, addr1, addr2] = await ethers.getSigners();
    
    // Deploy Diamond
    const DiamondCutFacet = await ethers.getContractFactory("DiamondCutFacet");
    diamondCutFacet = await DiamondCutFacet.deploy();
    await diamondCutFacet.deployed();

    const Diamond = await ethers.getContractFactory("Diamond");
    const diamond = await Diamond.deploy(owner.address, diamondCutFacet.address);
    await diamond.deployed();
    diamondAddress = diamond.address;

    diamondCutFacet = await ethers.getContractAt('DiamondCutFacet', diamondAddress);

    // Deploy and add ComplexStorageV3
    const ComplexStorageV3 = await ethers.getContractFactory("ComplexStorageV3");
    const v3Implementation = await ComplexStorageV3.deploy();
    await v3Implementation.deployed();

    await diamondCutFacet.diamondCut(
      [{
        facetAddress: v3Implementation.address,
        action: FacetCutAction.Add,
        functionSelectors: getSelectors(v3Implementation)
      }],
      ethers.constants.AddressZero,
      '0x'
    );

    complexStorageV3 = await ethers.getContractAt('ComplexStorageV3', diamondAddress);
  });

  describe("Upgrade Process", function() {
    it("should preserve existing data during upgrade", async function() {
      // Setup initial data in V3
      const initialValue = 100;
      const initialName = "Test User";
      await complexStorageV3.connect(addr1).addUserData(initialValue, initialName);
      
      // Deploy V4 implementation
      const ComplexStorageV4 = await ethers.getContractFactory("ComplexStorageV4");
      const v4Implementation = await ComplexStorageV4.deploy();
      await v4Implementation.deployed();

      // Upgrade to V4: First replace existing functions, then add new ones
      const v3Selectors = getSelectors(complexStorageV3);
      const v4Selectors = getSelectors(v4Implementation);
      const newSelectors = v4Selectors.remove(v3Selectors);

      // Deploy initializer
      const StorageInitializer = await ethers.getContractFactory("StorageInitializer");
      const initializer = await StorageInitializer.deploy();
      await initializer.deployed();

      await diamondCutFacet.connect(owner).diamondCut(
        [
          {
            facetAddress: v4Implementation.address,
            action: FacetCutAction.Replace,
            functionSelectors: v3Selectors
          },
          {
            facetAddress: v4Implementation.address,
            action: FacetCutAction.Add,
            functionSelectors: newSelectors
          }
        ],
        initializer.address,
        initializer.interface.encodeFunctionData('initialize', [[addr1.address]])
      );

      complexStorageV4 = await ethers.getContractAt('ComplexStorageV4', diamondAddress);

      // Verify old data is preserved
      const [details, indexes, updateCount, totalValue] = await complexStorageV4.getUserData(addr1.address);
      expect(details.value).to.equal(initialValue);
      expect(details.name).to.equal(initialName);
      expect(details.active).to.be.true;
      expect(totalValue).to.equal(initialValue); // New field should be initialized
    });

    it("should support new functionality after upgrade", async function() {
      const groupId = 1;
      await complexStorageV4.connect(addr1).addToGroup(groupId);
      await complexStorageV4.connect(addr2).addToGroup(groupId);

      // Add new data using V4 functionality
      await complexStorageV4.connect(addr1).addUserData(200, "Updated Name");
      await complexStorageV4.connect(addr2).addUserData(300, "Second User");

      // Test new function
      // First user: initial 100 + new 200 = 300
      // Second user: new 300 = 300
      // Total group value should be 600
      const totalGroupValue = await complexStorageV4.getTotalValueInGroup(groupId);
      expect(totalGroupValue).to.equal(600);

      // Verify timestamp is recorded
      const [details] = await complexStorageV4.getUserData(addr1.address);
      expect(details.value).to.equal(200);
    });

    it("should maintain correct history across versions", async function() {
      // Get history from latest update
      const historyEntry = await complexStorageV4.getUserHistory(addr1.address, 1);
      expect(historyEntry.value).to.equal(200);
      expect(historyEntry.name).to.equal("Updated Name");
      expect(historyEntry.active).to.be.true;
      expect(historyEntry.active).to.be.true; // No lastUpdateTime in v3 struct
    });
  });

  describe("Error Cases After Upgrade", function() {
    it("should maintain error conditions", async function() {
      const groupId = 2;
      // Fill up group
      const signers = await ethers.getSigners();
      for(let i = 0; i < 10; i++) {
        await complexStorageV4.connect(signers[i]).addToGroup(groupId);
      }

      // Verify error still works
      try {
        await complexStorageV4.connect(signers[10]).addToGroup(groupId);
        expect.fail("Should have reverted");
      } catch (error) {
        expect(error.message).to.include("GroupFull");
      }
    });
  });
});
