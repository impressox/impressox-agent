/* global ethers describe before it */
/* eslint-disable prefer-const */

const { deployDiamond } = require('../scripts/deploy.js')
const { FacetCutAction } = require('../scripts/libraries/diamond.js')
const { assert } = require('chai')

describe('Cache bug test', async () => {
  let diamondLoupeFacet
  let test1Facet
  const ownerSel = '0x8da5cb5b'

  const sel0 = '0x19e3b533' // fills up slot 1
  const sel1 = '0x0716c2ae' // fills up slot 1
  const sel2 = '0x11046047' // fills up slot 1
  const sel3 = '0xcf3bbe18' // fills up slot 1
  const sel4 = '0x24c1d5a7' // fills up slot 1
  const sel5 = '0xcbb835f6' // fills up slot 1
  const sel6 = '0xcbb835f7' // fills up slot 1
  const sel7 = '0xcbb835f8' // fills up slot 2
  const sel8 = '0xcbb835f9' // fills up slot 2
  const sel9 = '0xcbb835fa' // fills up slot 2
  const sel10 = '0xcbb835fb' // fills up slot 2

  before(async function () {
    let tx
    let receipt

    let selectors = [
      sel0,
      sel1,
      sel2,
      sel3,
      sel4,
      sel5,
      sel6,
      sel7,
      sel8,
      sel9,
      sel10
    ]

    let diamondAddress = await deployDiamond()
    let diamondCutFacet = await ethers.getContractAt('DiamondCutFacet', diamondAddress)
    diamondLoupeFacet = await ethers.getContractAt('DiamondLoupeFacet', diamondAddress)
    const Test1Facet = await ethers.getContractFactory('Test1Facet')
    test1Facet = await Test1Facet.deploy()
    await test1Facet.deployed()

    // add functions
    tx = await diamondCutFacet.diamondCut([
      {
        facetAddress: test1Facet.address,
        action: FacetCutAction.Add,
        functionSelectors: selectors
      }
    ], ethers.constants.AddressZero, '0x', { gasLimit: 800000 })
    receipt = await tx.wait()
    if (!receipt.status) {
      throw Error(`Diamond upgrade failed: ${tx.hash}`)
    }

    // Remove function selectors
    selectors = [
      ownerSel, // owner selector
      sel0,     // first slot selector
      sel5,     // middle slot selector
      sel10     // last slot selector
    ]
    tx = await diamondCutFacet.diamondCut([
      {
        facetAddress: ethers.constants.AddressZero,
        action: FacetCutAction.Remove,
        functionSelectors: selectors
      }
    ], ethers.constants.AddressZero, '0x', { gasLimit: 800000 })
    receipt = await tx.wait()
    if (!receipt.status) {
      throw Error(`Diamond upgrade failed: ${tx.hash}`)
    }
  })

  it('should not exhibit the cache bug', async () => {
    // Get the test1Facet's registered functions
    let selectors = await diamondLoupeFacet.facetFunctionSelectors(test1Facet.address)

    // Check removed selectors
    assert.isFalse(selectors.includes(sel0), 'Contains sel0')
    assert.isFalse(selectors.includes(sel5), 'Contains sel5')
    assert.isFalse(selectors.includes(sel10), 'Contains sel10')
    assert.isFalse(selectors.includes(ownerSel), 'Contains ownerSel')

    // Check remaining selectors
    assert.isTrue(selectors.includes(sel1), 'Does not contain sel1')
    assert.isTrue(selectors.includes(sel2), 'Does not contain sel2')
    assert.isTrue(selectors.includes(sel3), 'Does not contain sel3')
    assert.isTrue(selectors.includes(sel4), 'Does not contain sel4')
    assert.isTrue(selectors.includes(sel6), 'Does not contain sel6')
    assert.isTrue(selectors.includes(sel7), 'Does not contain sel7')
    assert.isTrue(selectors.includes(sel8), 'Does not contain sel8')
    assert.isTrue(selectors.includes(sel9), 'Does not contain sel9')

    // Check total number of selectors
    assert.equal(selectors.length, 8, 'Incorrect number of selectors')
  })

  it('should maintain correct selector presence after removal', async () => {
    const selectors = [...await diamondLoupeFacet.facetFunctionSelectors(test1Facet.address)]
    const expectedSelectors = [sel1, sel2, sel3, sel4, sel6, sel7, sel8, sel9]
    assert.sameMembers(selectors, expectedSelectors, 'Selector set is incorrect')
  })

  it('should handle multiple removals in different slots', async () => {
    const diamondAddress = await deployDiamond()
    const diamondCutFacet = await ethers.getContractAt('DiamondCutFacet', diamondAddress)
    const diamondLoupeFacet = await ethers.getContractAt('DiamondLoupeFacet', diamondAddress)
    const Test1Facet = await ethers.getContractFactory('Test1Facet')
    const test1Facet = await Test1Facet.deploy()
    await test1Facet.deployed()

    // Add selectors in multiple slots
    const selectors = [
      '0x11111111', '0x22222222', '0x33333333', '0x44444444', // Slot 1
      '0x55555555', '0x66666666', '0x77777777', '0x88888888', // Slot 2
      '0x99999999', '0xaaaaaaaa', '0xbbbbbbbb', '0xcccccccc'  // Slot 3
    ]

    // Add all selectors
    let tx = await diamondCutFacet.diamondCut([
      {
        facetAddress: test1Facet.address,
        action: FacetCutAction.Add,
        functionSelectors: selectors
      }
    ], ethers.constants.AddressZero, '0x', { gasLimit: 800000 })
    await tx.wait()

    // Remove selectors from different slots
    const removals = ['0x22222222', '0x66666666', '0xaaaaaaaa']
    tx = await diamondCutFacet.diamondCut([
      {
        facetAddress: ethers.constants.AddressZero,
        action: FacetCutAction.Remove,
        functionSelectors: removals
      }
    ], ethers.constants.AddressZero, '0x', { gasLimit: 800000 })
    await tx.wait()

    // Verify remaining selectors
    const remainingSelectors = await diamondLoupeFacet.facetFunctionSelectors(test1Facet.address)
    const expectedRemaining = selectors.filter(s => !removals.includes(s))
    assert.sameMembers(remainingSelectors, expectedRemaining, 'Incorrect remaining selectors')
  })

  it('should handle edge case of removing all selectors from a slot', async () => {
    const diamondAddress = await deployDiamond()
    const diamondCutFacet = await ethers.getContractAt('DiamondCutFacet', diamondAddress)
    const diamondLoupeFacet = await ethers.getContractAt('DiamondLoupeFacet', diamondAddress)
    const Test1Facet = await ethers.getContractFactory('Test1Facet')
    const test1Facet = await Test1Facet.deploy()
    await test1Facet.deployed()

    // Add selectors in multiple slots
    const selectors = [
      '0x11111111', '0x22222222', '0x33333333', '0x44444444', // Slot 1
      '0x55555555', '0x66666666', '0x77777777', '0x88888888'  // Slot 2
    ]

    // Add all selectors
    let tx = await diamondCutFacet.diamondCut([
      {
        facetAddress: test1Facet.address,
        action: FacetCutAction.Add,
        functionSelectors: selectors
      }
    ], ethers.constants.AddressZero, '0x', { gasLimit: 800000 })
    await tx.wait()

    // Remove all selectors from slot 1
    const removals = ['0x11111111', '0x22222222', '0x33333333', '0x44444444']
    tx = await diamondCutFacet.diamondCut([
      {
        facetAddress: ethers.constants.AddressZero,
        action: FacetCutAction.Remove,
        functionSelectors: removals
      }
    ], ethers.constants.AddressZero, '0x', { gasLimit: 800000 })
    await tx.wait()

    // Verify remaining selectors
    const remainingSelectors = await diamondLoupeFacet.facetFunctionSelectors(test1Facet.address)
    const expectedRemaining = selectors.filter(s => !removals.includes(s))
    assert.sameMembers(remainingSelectors, expectedRemaining, 'Incorrect remaining selectors')
  })
})
