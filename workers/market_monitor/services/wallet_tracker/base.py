from typing import Dict, List, Optional
from datetime import datetime
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class Chain(Enum):
    ETHEREUM = "ethereum"
    BSC = "bsc"
    BASE = "base"
    SOLANA = "solana"

    @property
    def rpc_url(self) -> str:
        from workers.market_monitor.utils.config import get_config
        config = get_config()
        return config.get_rpc_url(self.value)

    @property
    def w3(self):
        if self.value == "solana":
            return None
        from web3 import Web3
        return Web3(Web3.HTTPProvider(self.rpc_url))

    @property
    def solana_client(self):
        if self.value == "solana":
            from solana.rpc.async_api import AsyncClient
            from solana.rpc.commitment import Finalized
            return AsyncClient(self.rpc_url, commitment=Finalized)
        return None

class WalletType(Enum):
    EVM = "evm"
    SOLANA = "solana"

def validate_wallet_address(address: str) -> tuple[WalletType, bool]:
    """Validate wallet address and determine its type"""
    try:
        # Check if it's a valid Solana address using solders.pubkey
        try:
            from solders.pubkey import Pubkey
            pubkey = Pubkey.from_string(address)
            if pubkey:
                return WalletType.SOLANA, True
        except Exception as e:
            logger.debug(f"[WalletWatcher] Not a valid Solana address: {e}")

        # Check if it's a valid EVM address using web3
        from web3 import Web3
        if Web3.is_address(address):
            # Additional check for checksum address
            checksum_address = Web3.to_checksum_address(address)
            if checksum_address:
                return WalletType.EVM, True

        return None, False
    except Exception as e:
        logger.error(f"[WalletWatcher] Error validating wallet address {address}: {e}")
        return None, False

class ActivityType(Enum):
    NATIVE_TRANSFER_IN = "native_transfer_in"
    NATIVE_TRANSFER_OUT = "native_transfer_out"
    TOKEN_TRANSFER_IN = "token_transfer_in"
    TOKEN_TRADE = "token_trade"
    NFT_TRANSFER_IN = "nft_transfer_in"
    NFT_TRADE = "nft_trade" 