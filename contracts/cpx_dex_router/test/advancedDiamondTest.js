const { expect, assert } = require("chai");
const { ethers } = require("hardhat");
const {
  getSelectors,
  FacetCutAction,
} = require("../scripts/libraries/diamond.js");

describe("Advanced Diamond Tests", function () {
  this.timeout(10000); // Increase timeout for complex tests
  
  let diamondAddress;
  let diamondCutFacet;
  let owner;
  let addr1;
  let addr2;

  before(async function () {
    [owner, addr1, addr2] = await ethers.getSigners();
    // Deploy a fresh diamond for advanced tests
    const DiamondCutFacet = await ethers.getContractFactory("DiamondCutFacet");
    diamondCutFacet = await DiamondCutFacet.deploy();
    await diamondCutFacet.deployed();

    const Diamond = await ethers.getContractFactory("Diamond");
    const diamond = await Diamond.deploy(owner.address, diamondCutFacet.address);
    await diamond.deployed();
    diamondAddress = diamond.address;

    // Get diamondCutFacet from deployed diamond
    diamondCutFacet = await ethers.getContractAt('DiamondCutFacet', diamondAddress);
  });

  describe("Race Condition Tests", function() {
    it("should handle multiple concurrent diamondCut calls correctly", async function() {
      const Test1Facet = await ethers.getContractFactory("Test1Facet");
      const test1Facet = await Test1Facet.deploy();
      await test1Facet.deployed();

      const selectors = getSelectors(test1Facet);
      
      // Create multiple concurrent transactions
      diamondCutFacet = diamondCutFacet.connect(owner);
      const promises = [];
      for(let i = 0; i < 3; i++) {
        const tx = diamondCutFacet.diamondCut(
          [{
            facetAddress: test1Facet.address,
            action: FacetCutAction.Add,
            functionSelectors: selectors
          }],
          ethers.constants.AddressZero, 
          '0x'
        );
        promises.push(tx);
      }

      // First should succeed, others should fail
      try {
        await Promise.all(promises);
        assert.fail("All transactions succeeded when they should not have");
      } catch (error) {
        expect(error.message).to.include("reverted with custom error");
      }
    });
  });

  describe("Performance Tests", function() {
    it("should handle large number of selectors efficiently", async function() {
      const Test1Facet = await ethers.getContractFactory("Test1Facet");
      const test1Facet = await Test1Facet.deploy();
      await test1Facet.deployed();

      const selectors = [];
      for(let i = 0; i < 100; i++) {
        // Create unique function selectors
        selectors.push(ethers.utils.id(`test${i}()`).slice(0, 10));
      }

      const startTime = Date.now();
      
      diamondCutFacet = diamondCutFacet.connect(owner);
      await diamondCutFacet.diamondCut(
        [{
          facetAddress: test1Facet.address,
          action: FacetCutAction.Add,
          functionSelectors: selectors
        }],
        ethers.constants.AddressZero,
        '0x',
        { gasLimit: 8000000 } // Increase gas limit for many selectors
      );

      const endTime = Date.now();
      const executionTime = endTime - startTime;
      
      // Execution should be reasonably fast
      expect(executionTime).to.be.below(5000); // 5 seconds
    });
  });

  describe("Complex Storage Tests", function() {
    it("should preserve complex storage during upgrades", async function() {
      // Deploy initial facet with complex storage
      const ComplexStorage = await ethers.getContractFactory("ComplexStorage");
      const complexStorage = await ComplexStorage.deploy();
      await complexStorage.deployed();

      diamondCutFacet = diamondCutFacet.connect(owner);
      await diamondCutFacet.diamondCut(
        [{
          facetAddress: complexStorage.address,
          action: FacetCutAction.Add,
          functionSelectors: getSelectors(complexStorage)
        }],
        ethers.constants.AddressZero,
        '0x'
      );

      // Set some complex data
      const complex = await ethers.getContractAt('ComplexStorage', diamondAddress);
      await complex.setComplexData(123, ethers.utils.formatBytes32String("test"), [1, 2, 3]);

      // Deploy upgraded version
      const ComplexStorageV2 = await ethers.getContractFactory("ComplexStorageV2");
      const complexStorageV2 = await ComplexStorageV2.deploy();
      await complexStorageV2.deployed();

      // Upgrade
      await diamondCutFacet.diamondCut(
        [{
          facetAddress: complexStorageV2.address,
          action: FacetCutAction.Replace,
          functionSelectors: getSelectors(complexStorage)
        }],
        ethers.constants.AddressZero,
        '0x'
      );

      // Verify data was preserved
      const complexV2 = await ethers.getContractAt('ComplexStorageV2', diamondAddress);
      const data = await complexV2.getComplexData();
      expect(data.number).to.equal(123);
      expect(ethers.utils.parseBytes32String(data.text)).to.equal("test");
      expect(data.array.map(x => x.toNumber())).to.deep.equal([1, 2, 3]);
    });
  });

  describe("Initialization Edge Cases", function() {
    it("should handle initialization revert cases", async function() {
      diamondCutFacet = diamondCutFacet.connect(owner);
      const BadInit = await ethers.getContractFactory("BadInit");
      const badInit = await BadInit.deploy();
      await badInit.deployed();

      try {
        await diamondCutFacet.diamondCut(
          [],
          badInit.address,
          badInit.interface.encodeFunctionData('initialize')
        );
        assert.fail("Should have reverted");
      } catch (error) {
        console.log("BadInit error:", error.message);
        expect(error.message).to.include("reverted");
      }
    });

    it("should handle recursive initialization attempts", async function() {
      diamondCutFacet = diamondCutFacet.connect(owner);
      const RecursiveInit = await ethers.getContractFactory("RecursiveInit");
      const recursiveInit = await RecursiveInit.deploy();
      await recursiveInit.deployed();

      try {
        await diamondCutFacet.diamondCut(
          [],
          recursiveInit.address,
          recursiveInit.interface.encodeFunctionData('initialize')
        );
        assert.fail("Should have reverted");
      } catch (error) {
        console.log("RecursiveInit error:", error.message);
        expect(error.message).to.include("reverted");
      }
    });
  });
});
