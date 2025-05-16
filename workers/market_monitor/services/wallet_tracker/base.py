import base58
import logging
from enum import Enum
from typing import Tuple, Dict, Optional
from solders.pubkey import Pubkey
from web3 import AsyncWeb3
from eth_utils import is_address

from workers.market_monitor.utils.config import get_config

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Finalized

logger = logging.getLogger(__name__)

# Initialize Web3 instances dictionary at module level
_w3_instances: Dict[str, AsyncWeb3] = {}
_solana_client: Optional[AsyncClient] = None

class Chain(Enum):
    ETHEREUM = "ethereum"
    BSC = "bsc"
    BASE = "base"
    SOLANA = "solana"
    
    @property
    def rpc_url(self) -> str:
        config = get_config()
        return config.get_rpc_url(self.value)

    @property
    def w3(self) -> AsyncWeb3:
        if self is Chain.SOLANA:
            return None
        
        logger.info(f"[Chain] Fetching {self.value}")
        if self.value not in _w3_instances:
            _w3_instances[self.value] = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(self.rpc_url))
        return _w3_instances[self.value]

    @property
    def solana_client(self):
        if self is Chain.SOLANA:
            global _solana_client
            if _solana_client is None:
                _solana_client = AsyncClient(self.rpc_url, commitment=Finalized) 
            return _solana_client
        return None

    @classmethod
    async def cleanup(cls):
        """Cleanup all Web3 instances"""
        for w3 in _w3_instances.values():
            if w3 and w3.provider:
                await w3.provider.disconnect()
        _w3_instances.clear()
        
        global _solana_client
        if _solana_client:
            await _solana_client.close()
            _solana_client = None

class WalletType(Enum):
    EVM = "evm"
    SOLANA = "solana"

class ActivityType(Enum):
    NATIVE_TRANSFER_IN = "native_transfer_in"
    NATIVE_TRANSFER_OUT = "native_transfer_out"
    TOKEN_TRANSFER_IN   = "token_transfer_in"
    TOKEN_TRADE         = "token_trade"
    NFT_TRANSFER_IN     = "nft_transfer_in"
    NFT_TRADE           = "nft_trade"


def validate_wallet_address(address: str) -> Tuple[WalletType, bool]:
    # Solana check
    try:
        data = base58.b58decode(address)
        if len(data) == 32:
            return WalletType.SOLANA, True
    except Exception:
        pass
    # EVM check
    if is_address(address):
        return WalletType.EVM, True
    return None, False