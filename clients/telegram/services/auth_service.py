import os
import httpx
import json
import asyncio
from datetime import datetime, timedelta
from clients.config import DEX_AGGREGATOR_URL
from clients.telegram.utils.logger import logger
from clients.telegram.utils.redis_util import get_redis_client
from clients.telegram.services.wallet_service import get_wallet_service

class AuthService:
    def __init__(self):
        self.auth_url = f"{DEX_AGGREGATOR_URL}/auth/telegram"
        self.redis_client = get_redis_client()
        self.token_prefix = "cpx_auth_token:"
        self.token_expiry = timedelta(days=7)  # Token expires in 7 days
        self.wallet_service = get_wallet_service()
        self.token = None
        self.is_new_user = False
        self.user = None
        self.wallets = []

    async def get_stored_token(self, telegram_id: str) -> dict:
        """Get stored token from Redis"""
        try:
            token_data = self.redis_client.get(f"{self.token_prefix}{telegram_id}")
            if token_data:
                return json.loads(token_data)
        except Exception as e:
            logger.error(f"Error getting stored token: {e}")
        return None

    async def store_token(self, telegram_id: str, token_data: dict):
        """Store token in Redis"""
        try:
            self.redis_client.set(
                f"{self.token_prefix}{telegram_id}",
                json.dumps(token_data),
                ex=int(self.token_expiry.total_seconds())
            )
            # Update instance variables
            self.token = token_data.get("token")
            self.is_new_user = token_data.get("isNewUser", False)
            self.user = token_data.get("user")
            self.wallets = token_data.get("wallets", [])
        except Exception as e:
            logger.error(f"Error storing token: {e}")

    async def refresh_token(self, telegram_id: str, name: str, email: str = None) -> dict:
        """Refresh token by re-authenticating with API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.auth_url,
                    json={
                        "telegramId": str(telegram_id),
                        "name": name,
                        "email": email
                    }
                )
                response.raise_for_status()
                data = response.json()

                # Ensure all wallet types exist
                wallets = await self.wallet_service.ensure_all_wallets_exist(data["access_token"])

                # Prepare token data
                token_data = {
                    "token": data["access_token"],
                    "isNewUser": not data.get("user", {}).get("telegramId"),
                    "user": data.get("user", {}),
                    "wallets": wallets,
                    "created_at": datetime.utcnow().isoformat()
                }

                # Store new token
                await self.store_token(telegram_id, token_data)
                return token_data

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return None

    async def authenticate_user(self, telegram_id: str, name: str, email: str = None) -> dict:
        """
        Authenticate user with DEX aggregator API
        Returns:
            dict: {
                "token": str,
                "isNewUser": bool,
                "user": dict,
                "wallets": List[dict]
            }
        """
        try:
            # Check for stored token first
            stored_token = await self.get_stored_token(telegram_id)
            if stored_token:
                try:
                    # Try to use stored token
                    wallets = await self.wallet_service.ensure_all_wallets_exist(stored_token["token"])
                    stored_token["wallets"] = wallets
                    # Update instance variables
                    self.token = stored_token["token"]
                    self.is_new_user = stored_token.get("isNewUser", False)
                    self.user = stored_token.get("user")
                    self.wallets = wallets
                    return stored_token
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        # Token expired, refresh it
                        logger.info(f"Token expired for user {telegram_id}, refreshing...")
                        return await self.refresh_token(telegram_id, name, email)
                    raise e

            # If no stored token, authenticate with API
            return await self.refresh_token(telegram_id, name, email)

        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return None

    def ensure_authenticated(self, telegram_id: str, name: str, email: str = None):
        """
        Run authentication in a separate task without blocking the main flow
        """
        async def _auth_task():
            try:
                return await self.authenticate_user(telegram_id, name, email)
            except Exception as e:
                logger.error(f"Error in auth task: {e}")
                return None

        # Create and start task without awaiting
        asyncio.create_task(_auth_task())

# Singleton instance
_auth_service = None

def get_auth_service() -> AuthService:
    """Get or create auth service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service 