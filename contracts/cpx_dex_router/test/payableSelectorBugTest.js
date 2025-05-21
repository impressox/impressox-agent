/* global ethers describe before it */
/* eslint-disable prefer-const */

const { deployDiamond } = require("../scripts/deploy.js");

const { FacetCutAction } = require("../scripts/libraries/diamond.js");

const { assert } = require("chai");

// The diamond example comes with 8 function selectors
// [cut, loupe, loupe, loupe, loupe, erc165, transferOwnership, owner]
// This bug manifests if you add the payableSelector(0x00000000) to the 1st slot in a fresh row and remove it
// We Add 8 more random selectors to the diamond, then add the payable selector to the 1st slot in a fresh row
// [cut, loupe, loupe, loupe, loupe, erc165, transferOwnership, owner]
// [rand1, rand2, rand3, rand4, rand5, rand6, rand7, rand8]
// [payableSelector]
// We then remove the payable selector from the diamond, this causes malfunction in the slot tracking
// And `rand8` is lost from the selector tracking
describe("Payable selector bug test", async () => {
  it("Should not revert with missing selector if removal of payable selector @ selectorCount % 8", async () => {
    let diamondAddress = await deployDiamond();
    let diamondCutFacet = await ethers.getContractAt(
      "DiamondCutFacet",
      diamondAddress
    );
    const diamondLoupeFacet = await ethers.getContractAt(
      "DiamondLoupeFacet",
      diamondAddress
    );
    const Test1Facet = await ethers.getContractFactory("Test1Facet");
    const test1Facet = await Test1Facet.deploy();
    await test1Facet.deployed();

    const payableSelector = "0x00000000";

    const existingSelectors = await diamondLoupeFacet.facets();

    const selectorCount = existingSelectors.reduce((acc, x) => {
      return acc + x.functionSelectors.length;
    }, 0);

    const numberOfSelectorsToAdd = 8 - (selectorCount % 8);

    const selectors = [];
    for (let i = 0; i < numberOfSelectorsToAdd; i++) {
      selectors.push(ethers.utils.hexlify(ethers.utils.randomBytes(4)));
    }

    // Push the selector into a new row
    selectors.push(payableSelector);

    tx = await diamondCutFacet.diamondCut(
      [
        {
          facetAddress: test1Facet.address,
          action: FacetCutAction.Add,
          functionSelectors: selectors,
        },
      ],
      ethers.constants.AddressZero,
      "0x",
      { gasLimit: 800000 }
    );

    receipt = await tx.wait();

    tx = await diamondCutFacet.diamondCut(
      [
        {
          facetAddress: ethers.constants.AddressZero,
          action: FacetCutAction.Remove,
          functionSelectors: [payableSelector],
        },
      ],
      ethers.constants.AddressZero,
      "0x",
      { gasLimit: 800000 }
    );

    receipt = await tx.wait();

    assert.deepEqual(
      await diamondLoupeFacet.facetFunctionSelectors(test1Facet.address),
      selectors.filter((x) => x != payableSelector)
    );
  });

  // This set of tests fuzzes the fix, it adds the payable(0x00000000) selector to every selectorSlotIndex, removes it and checks all other selectors a unaffected
  for (let numSelectorsToAdd = 0; numSelectorsToAdd < 10; numSelectorsToAdd++) {
    it("Should not revert with missing selector if removal of payable selector @ selectorCount % 8", async () => {
      let diamondAddress = await deployDiamond();
      let diamondCutFacet = await ethers.getContractAt(
        "DiamondCutFacet",
        diamondAddress
      );
      const diamondLoupeFacet = await ethers.getContractAt(
        "DiamondLoupeFacet",
        diamondAddress
      );
      const Test1Facet = await ethers.getContractFactory("Test1Facet");
      const test1Facet = await Test1Facet.deploy();
      await test1Facet.deployed();

      const payableSelector = "0x00000000";

      const selectors = [];
      for (let i = 0; i < numSelectorsToAdd; i++) {
        selectors.push(ethers.utils.hexlify(ethers.utils.randomBytes(4)));
      }

      // Push the selector into a new row
      selectors.push(payableSelector);

      tx = await diamondCutFacet.diamondCut(
        [
          {
            facetAddress: test1Facet.address,
            action: FacetCutAction.Add,
            functionSelectors: selectors,
          },
        ],
        ethers.constants.AddressZero,
        "0x",
        { gasLimit: 800000 }
      );

      receipt = await tx.wait();

      tx = await diamondCutFacet.diamondCut(
        [
          {
            facetAddress: ethers.constants.AddressZero,
            action: FacetCutAction.Remove,
            functionSelectors: [payableSelector],
          },
        ],
        ethers.constants.AddressZero,
        "0x",
        { gasLimit: 800000 }
      );

      receipt = await tx.wait();

      assert.deepEqual(
        await diamondLoupeFacet.facetFunctionSelectors(test1Facet.address),
        selectors.filter((x) => x != payableSelector)
      );
    });
  }

  // New test cases
  it("should handle multiple payable selectors in different slots", async () => {
    let diamondAddress = await deployDiamond();
    let diamondCutFacet = await ethers.getContractAt(
      "DiamondCutFacet",
      diamondAddress
    );
    const diamondLoupeFacet = await ethers.getContractAt(
      "DiamondLoupeFacet",
      diamondAddress
    );
    const Test1Facet = await ethers.getContractFactory("Test1Facet");
    const test1Facet = await Test1Facet.deploy();
    await test1Facet.deployed();

    const payableSelector1 = "0x00000000";
    const payableSelector2 = "0x00000001";
    const selectors = [];

    // Add selectors to fill multiple slots
    for (let i = 0; i < 16; i++) {
      selectors.push(ethers.utils.hexlify(ethers.utils.randomBytes(4)));
    }

    // Add payable selectors at different positions
    selectors.splice(4, 0, payableSelector1);  // Slot 1
    selectors.splice(12, 0, payableSelector2); // Slot 2

    // Add all selectors
    let tx = await diamondCutFacet.diamondCut(
      [
        {
          facetAddress: test1Facet.address,
          action: FacetCutAction.Add,
          functionSelectors: selectors,
        },
      ],
      ethers.constants.AddressZero,
      "0x",
      { gasLimit: 800000 }
    );
    await tx.wait();

    // Remove both payable selectors
    tx = await diamondCutFacet.diamondCut(
      [
        {
          facetAddress: ethers.constants.AddressZero,
          action: FacetCutAction.Remove,
          functionSelectors: [payableSelector1, payableSelector2],
        },
      ],
      ethers.constants.AddressZero,
      "0x",
      { gasLimit: 800000 }
    );
    await tx.wait();

    // Verify remaining selectors
    const remainingSelectors = await diamondLoupeFacet.facetFunctionSelectors(test1Facet.address);
    const expectedRemaining = selectors.filter(x => x !== payableSelector1 && x !== payableSelector2);
    assert.sameMembers(remainingSelectors, expectedRemaining, "Incorrect remaining selectors");
  });

  it("should handle edge case of removing payable selector from last slot", async () => {
    let diamondAddress = await deployDiamond();
    let diamondCutFacet = await ethers.getContractAt(
      "DiamondCutFacet",
      diamondAddress
    );
    const diamondLoupeFacet = await ethers.getContractAt(
      "DiamondLoupeFacet",
      diamondAddress
    );
    const Test1Facet = await ethers.getContractFactory("Test1Facet");
    const test1Facet = await Test1Facet.deploy();
    await test1Facet.deployed();

    const payableSelector = "0x00000000";
    const selectors = [];

    // Add selectors to fill exactly one slot
    for (let i = 0; i < 7; i++) {
      selectors.push(ethers.utils.hexlify(ethers.utils.randomBytes(4)));
    }

    // Add payable selector as the last selector
    selectors.push(payableSelector);

    // Add all selectors
    let tx = await diamondCutFacet.diamondCut(
      [
        {
          facetAddress: test1Facet.address,
          action: FacetCutAction.Add,
          functionSelectors: selectors,
        },
      ],
      ethers.constants.AddressZero,
      "0x",
      { gasLimit: 800000 }
    );
    await tx.wait();

    // Remove payable selector
    tx = await diamondCutFacet.diamondCut(
      [
        {
          facetAddress: ethers.constants.AddressZero,
          action: FacetCutAction.Remove,
          functionSelectors: [payableSelector],
        },
      ],
      ethers.constants.AddressZero,
      "0x",
      { gasLimit: 800000 }
    );
    await tx.wait();

    // Verify remaining selectors
    const remainingSelectors = await diamondLoupeFacet.facetFunctionSelectors(test1Facet.address);
    const expectedRemaining = selectors.filter(x => x !== payableSelector);
    assert.sameMembers(remainingSelectors, expectedRemaining, "Incorrect remaining selectors");
  });

  it("should handle adding and removing payable selector multiple times", async () => {
    let diamondAddress = await deployDiamond();
    let diamondCutFacet = await ethers.getContractAt(
      "DiamondCutFacet",
      diamondAddress
    );
    const diamondLoupeFacet = await ethers.getContractAt(
      "DiamondLoupeFacet",
      diamondAddress
    );
    const Test1Facet = await ethers.getContractFactory("Test1Facet");
    const test1Facet = await Test1Facet.deploy();
    await test1Facet.deployed();

    const payableSelector = "0x00000000";
    const selectors = [];

    // Add some initial selectors
    for (let i = 0; i < 8; i++) {
      selectors.push(ethers.utils.hexlify(ethers.utils.randomBytes(4)));
    }

    // Add initial selectors
    let tx = await diamondCutFacet.diamondCut(
      [
        {
          facetAddress: test1Facet.address,
          action: FacetCutAction.Add,
          functionSelectors: selectors,
        },
      ],
      ethers.constants.AddressZero,
      "0x",
      { gasLimit: 800000 }
    );
    await tx.wait();

    // Add and remove payable selector multiple times
    for (let i = 0; i < 3; i++) {
      // Add payable selector
      tx = await diamondCutFacet.diamondCut(
        [
          {
            facetAddress: test1Facet.address,
            action: FacetCutAction.Add,
            functionSelectors: [payableSelector],
          },
        ],
        ethers.constants.AddressZero,
        "0x",
        { gasLimit: 800000 }
      );
      await tx.wait();

      // Remove payable selector
      tx = await diamondCutFacet.diamondCut(
        [
          {
            facetAddress: ethers.constants.AddressZero,
            action: FacetCutAction.Remove,
            functionSelectors: [payableSelector],
          },
        ],
        ethers.constants.AddressZero,
        "0x",
        { gasLimit: 800000 }
      );
      await tx.wait();

      // Verify remaining selectors
      const remainingSelectors = await diamondLoupeFacet.facetFunctionSelectors(test1Facet.address);
      assert.sameMembers(remainingSelectors, selectors, "Incorrect remaining selectors after iteration " + i);
    }
  });
});
