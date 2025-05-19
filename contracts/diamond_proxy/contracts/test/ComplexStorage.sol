// SPDX-License-Identifier: MIT
pragma solidity 0.8.23;

contract ComplexStorage {
    struct ComplexData {
        uint256 number;
        bytes32 text;
        uint256[] array;
    }

    ComplexData internal data;

    function setComplexData(uint256 _number, bytes32 _text, uint256[] memory _array) external {
        data.number = _number;
        data.text = _text;
        data.array = _array;
    }

    function getComplexData() external view returns (ComplexData memory) {
        return data;
    }
}
