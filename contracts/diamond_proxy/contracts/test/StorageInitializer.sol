// SPDX-License-Identifier: MIT
pragma solidity 0.8.23;

contract StorageInitializer {
    // Storage layout must match exactly with V3 and V4
    struct InnerStruct {
        uint256 value;
        string name;
        bool active;
    }

    struct UserData {
        InnerStruct details;
        mapping(uint256 => InnerStruct) history;
        uint256[] indexes;
        uint256 updateCount;
    }

    struct StorageLayout {
        // V3 storage slots must be in exact same order
        mapping(address => UserData) users;
        mapping(uint256 => address[]) groupMembers;
        uint256 maxGroupSize;
        // V4 storage slot
        mapping(address => uint256) userTotalValues;
    }

    StorageLayout private s;

    function initialize(address[] calldata _users) external {
        // Initialize totalValues for all provided users
        for (uint256 i = 0; i < _users.length; i++) {
            address user = _users[i];
            UserData storage userData = s.users[user];
            if (userData.updateCount > 0) {
                s.userTotalValues[user] = userData.details.value;
            }
        }
    }
}
