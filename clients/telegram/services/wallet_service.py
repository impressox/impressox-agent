import os
import httpx
from typing import List, Dict
from clients.config import DEX_AGGREGATOR_URL, SUPPORTED_CHAINS
from clients.telegram.utils.logger import logger

class WalletService:
    def __init__(self):
        self.base_url = f"{DEX_AGGREGATOR_URL}/wallets"
        self.supported_chains = SUPPORTED_CHAINS

    async def get_user_wallets(self, token: str) -> List[Dict]:
        """Get all wallets for a user"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    headers={"Authorization": f"Bearer {token}"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting user wallets: {e}")
            return []

    async def create_wallet(self, token: str, chain_type: str, chain_id: int) -> Dict:
        """Create a new wallet for a user"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "chainType": chain_type,
                        "chainId": chain_id
                    }
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            return None

    async def ensure_all_wallets_exist(self, token: str) -> List[Dict]:
        """
        Ensure user has all supported wallet types
        Returns list of all user's wallets
        """
        try:
            # Get existing wallets
            existing_wallets = await self.get_user_wallets(token)
            existing_chain_types = {w["chainType"] for w in existing_wallets}

            # Create missing wallets
            for chain_type, chain_id in self.supported_chains.items():
                if chain_type not in existing_chain_types:
                    await self.create_wallet(token, chain_type, chain_id)

            # Return updated wallet list
            return await self.get_user_wallets(token)
        except Exception as e:
            logger.error(f"Error ensuring wallets exist: {e}")
            return []

# Singleton instance
_wallet_service = None

def get_wallet_service() -> WalletService:
    """Get or create wallet service instance"""
    global _wallet_service
    if _wallet_service is None:
        _wallet_service = WalletService()
    return _wallet_service 