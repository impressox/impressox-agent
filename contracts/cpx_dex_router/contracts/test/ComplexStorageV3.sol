// SPDX-License-Identifier: MIT
pragma solidity 0.8.23;

contract ComplexStorageV3 {
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
        // Keep slot for V4 compatibility
        mapping(address => uint256) userTotalValues;
    }

    StorageLayout private s;
    uint256 public constant MAX_GROUP_SIZE = 10;

    event DataUpdated(address indexed user, uint256 indexed value, string name);
    event GroupMemberAdded(uint256 indexed groupId, address indexed member);

    error GroupFull();
    error InvalidIndex();

    function addUserData(uint256 _value, string calldata _name) external {
        UserData storage userData = s.users[msg.sender];
        userData.details = InnerStruct({
            value: _value,
            name: _name,
            active: true
        });
        
        uint256 index = userData.updateCount;
        userData.history[index] = userData.details;
        userData.indexes.push(index);
        userData.updateCount++;

        emit DataUpdated(msg.sender, _value, _name);
    }

    function addToGroup(uint256 _groupId) external {
        if(s.groupMembers[_groupId].length >= MAX_GROUP_SIZE) {
            revert GroupFull();
        }
        
        s.groupMembers[_groupId].push(msg.sender);
        emit GroupMemberAdded(_groupId, msg.sender);
    }

    function getUserData(address _user) external view returns (
        InnerStruct memory details,
        uint256[] memory indexes,
        uint256 updateCount
    ) {
        UserData storage userData = s.users[_user];
        return (
            userData.details,
            userData.indexes,
            userData.updateCount
        );
    }

    function getUserHistory(address _user, uint256 _index) external view returns (InnerStruct memory) {
        UserData storage userData = s.users[_user];
        if(_index >= userData.updateCount) {
            revert InvalidIndex();
        }
        return userData.history[_index];
    }

    function getGroupMembers(uint256 _groupId) external view returns (address[] memory) {
        return s.groupMembers[_groupId];
    }
}
