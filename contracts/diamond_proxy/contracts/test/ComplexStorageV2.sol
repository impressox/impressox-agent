// SPDX-License-Identifier: MIT
pragma solidity 0.8.23;

contract ComplexStorageV2 {
    struct ComplexData {
        uint256 number;
        bytes32 text;
        uint256[] array;
    }

    ComplexData internal data;

    function getComplexData() external view returns (ComplexData memory) {
        return data;
    }

    // New function in V2
    function updateComplexData(uint256 _number, bytes32 _text, uint256[] memory _array) external {
        require(_number > 0, "Number must be positive");
        data.number = _number;
        data.text = _text;
        data.array = _array;
    }
}
