from typing import Dict, List, Optional
from workers.market_monitor.services.wallet_tracker.base import Chain, WalletType, ActivityType
from workers.market_monitor.services.wallet_tracker.solana_tracker import SolanaWalletTracker
from workers.market_monitor.services.wallet_tracker.evm_tracker import EVMWalletTracker
from workers.market_monitor.utils.config import get_config

__all__ = ['Chain', 'WalletType', 'ActivityType']

class WalletTrackerFactory:
    @staticmethod
    def create_tracker(chain: Chain):
        """Create wallet tracker for specific chain"""
        if chain == Chain.SOLANA:
            return SolanaWalletTracker()
        else:
            return EVMWalletTracker(chain, get_config())

    @staticmethod
    def get_wallet_type(address: str) -> tuple[WalletType, bool]:
        """Get wallet type and validity"""
        from .base import validate_wallet_address
        return validate_wallet_address(address)

    @staticmethod
    def get_chain_for_wallet(address: str) -> Optional[Chain]:
        """Get chain for wallet address"""
        wallet_type, is_valid = WalletTrackerFactory.get_wallet_type(address)
        if not is_valid:
            return None

        if wallet_type == WalletType.SOLANA:
            return Chain.SOLANA
        elif wallet_type == WalletType.EVM:
            # Default to Ethereum for EVM addresses
            return Chain.ETHEREUM
        return None

    # @staticmethod
    # async def cleanup():
    #     """Cleanup all Web3 instances"""
    #     await Chain.cleanup() 