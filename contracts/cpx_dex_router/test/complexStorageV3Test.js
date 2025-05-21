const { expect } = require("chai");
const { ethers } = require("hardhat");
const {
  getSelectors,
  FacetCutAction,
} = require("../scripts/libraries/diamond.js");

describe("ComplexStorageV3 Tests", function () {
  let diamondAddress;
  let diamondCutFacet;
  let complexStorageV3;
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
    const complexStorageV3Implementation = await ComplexStorageV3.deploy();
    await complexStorageV3Implementation.deployed();

    // Add ComplexStorageV3 functions
    await diamondCutFacet.diamondCut(
      [{
        facetAddress: complexStorageV3Implementation.address,
        action: FacetCutAction.Add,
        functionSelectors: getSelectors(complexStorageV3Implementation)
      }],
      ethers.constants.AddressZero,
      '0x'
    );

    // Get interface to ComplexStorageV3
    complexStorageV3 = await ethers.getContractAt('ComplexStorageV3', diamondAddress);
  });

  describe("User Data Management", function() {
    it("should store and retrieve user data correctly", async function() {
      const testValue = 123;
      const testName = "Test User";
      
      await complexStorageV3.connect(addr1).addUserData(testValue, testName);
      
      const userData = await complexStorageV3.getUserData(addr1.address);
      expect(userData.details.value).to.equal(testValue);
      expect(userData.details.name).to.equal(testName);
      expect(userData.details.active).to.be.true;
      expect(userData.updateCount).to.equal(1);
      expect(userData.indexes.length).to.equal(1);
      expect(userData.indexes[0]).to.equal(0);
    });

    it("should maintain correct history", async function() {
      const updates = [
        { value: 100, name: "First Update" },
        { value: 200, name: "Second Update" },
        { value: 300, name: "Third Update" }
      ];

      // Add multiple updates
      for (const update of updates) {
        await complexStorageV3.connect(addr1).addUserData(update.value, update.name);
      }

      // Check current data
      const userData = await complexStorageV3.getUserData(addr1.address);
      expect(userData.updateCount).to.equal(4); // Including the previous test
      expect(userData.indexes.length).to.equal(4);

      // Check history
      for (let i = 0; i < updates.length; i++) {
        const historyEntry = await complexStorageV3.getUserHistory(addr1.address, i + 1);
        expect(historyEntry.value).to.equal(updates[i].value);
        expect(historyEntry.name).to.equal(updates[i].name);
        expect(historyEntry.active).to.be.true;
      }
    });
  });

  describe("Group Management", function() {
    it("should handle group memberships correctly", async function() {
      const groupId = 1;
      
      // Add members to group
      await complexStorageV3.connect(addr1).addToGroup(groupId);
      await complexStorageV3.connect(addr2).addToGroup(groupId);

      // Check group members
      const members = await complexStorageV3.getGroupMembers(groupId);
      expect(members.length).to.equal(2);
      expect(members[0]).to.equal(addr1.address);
      expect(members[1]).to.equal(addr2.address);
    });

    it("should enforce max group size", async function() {
      const groupId = 2;
      
      // Try to add more than MAX_GROUP_SIZE members
      const signers = await ethers.getSigners();
      for (let i = 0; i < 10; i++) {
        await complexStorageV3.connect(signers[i]).addToGroup(groupId);
      }

      // 11th member should fail
      try {
        await complexStorageV3.connect(signers[10]).addToGroup(groupId);
        expect.fail("Should have reverted");
      } catch (error) {
        expect(error.message).to.include("GroupFull");
      }
    });
  });

  describe("Error Cases", function() {
    it("should handle invalid history index", async function() {
      try {
        await complexStorageV3.getUserHistory(addr1.address, 999);
        expect.fail("Should have reverted");
      } catch (error) {
        expect(error.message).to.include("InvalidIndex");
      }
    });

    it("should handle non-existent user data", async function() {
      const nonExistentUser = ethers.Wallet.createRandom().address;
      const userData = await complexStorageV3.getUserData(nonExistentUser);
      
      expect(userData.details.value).to.equal(0);
      expect(userData.details.name).to.equal("");
      expect(userData.details.active).to.be.false;
      expect(userData.updateCount).to.equal(0);
      expect(userData.indexes.length).to.equal(0);
    });
  });
});
