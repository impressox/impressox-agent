# services/wallet_watcher.py

import asyncio
import json
import logging
from typing import Dict, List
from datetime import datetime

from workers.market_monitor.services.base import BaseWatcher
from workers.market_monitor.shared.models import Rule
from workers.market_monitor.utils.api import call_api
from workers.market_monitor.utils.config import get_config
from workers.market_monitor.utils.mongo import MongoJSONEncoder

logger = logging.getLogger(__name__)

class WalletWatcher(BaseWatcher):
    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.balance_cache = {}  # Cache wallet balances
        self.tx_cache = {}  # Cache recent transactions
        self.watch_type = "wallet"
        self.watch_interval = 30  # Check more frequently for wallets

    async def watch_targets(self):
        """Watch wallet activities and check conditions"""
        try:
            # Get wallet data
            logger.info(f"[WalletWatcher] Checking activities for wallets: {list(self.watching_targets)}")
            
            # Get target_data from active rules
            target_data = {}
            for wallet in self.watching_targets:
                rules = await self.redis.hgetall(f"watch:active:wallet:{wallet}")
                for rule_json in rules.values():
                    rule = Rule.from_dict(json.loads(rule_json))
                    if rule.target_data:
                        target_data.update(rule.target_data)
                    break  # Only need data from one rule

            wallet_data = await self.get_wallet_data(list(self.watching_targets), target_data)
            if not wallet_data:
                logger.warning("[WalletWatcher] No wallet data received from API")
                return

            logger.info(f"[WalletWatcher] Received wallet data: {json.dumps(wallet_data, indent=2)}")

            # Get all active wallet rules
            active_rules = []
            for wallet in self.watching_targets:
                rules = await self.redis.hgetall(f"watch:active:wallet:{wallet}")
                logger.info(f"[WalletWatcher] Found {len(rules)} active rules for {wallet}")
                for rule_json in rules.values():
                    rule = Rule.from_dict(json.loads(rule_json))
                    active_rules.append(rule)

            # Check conditions for each rule
            if active_rules:
                logger.info(f"[WalletWatcher] Checking {len(active_rules)} rules against wallet data")
                await self.check_rules(active_rules, wallet_data)
            else:
                logger.warning("[WalletWatcher] No active rules found for watching wallets")

        except Exception as e:
            logger.error(f"[WalletWatcher] Error watching wallets: {e}")

    async def get_wallet_data(self, wallets: List[str], target_data: Dict = None) -> Dict:
        """Get current wallet data from blockchain API"""
        try:
            # Get wallet data from API
            logger.info(f"[WalletWatcher] Fetching data for wallets: {wallets}")
            
            # Get API URL and headers from config
            api_url = self.config.get_blockchain_api_url()
            api_key = self.config.get_blockchain_api_key()
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            
            # Get data for each wallet
            result = {}
            for wallet in wallets:
                # Get balance
                balance_response = await call_api(
                    f"{api_url}/balance",
                    method="GET",
                    params={"address": wallet},
                    headers=headers
                )
                
                # Get recent transactions
                tx_response = await call_api(
                    f"{api_url}/transactions",
                    method="GET",
                    params={
                        "address": wallet,
                        "limit": 10  # Get last 10 transactions
                    },
                    headers=headers
                )
                
                if balance_response.get("success") and tx_response.get("success"):
                    result[wallet] = {
                        "balance": balance_response.get("data", {}).get("balance", 0),
                        "transactions": tx_response.get("data", []),
                        "last_updated": datetime.utcnow().isoformat()
                    }
                else:
                    logger.warning(f"[WalletWatcher] Failed to get data for wallet {wallet}")
            
            return result
            
        except Exception as e:
            logger.error(f"[WalletWatcher] Error fetching wallet data: {e}", exc_info=True)
            return {}

    def evaluate_conditions(self, rule: Rule, wallet_data: Dict) -> List[Dict]:
        """Evaluate rule conditions against wallet data"""
        matches = []
        condition = rule.condition or {"type": "any"}
        logger.info(f"[WalletWatcher] Evaluating conditions for rule {rule.rule_id}: {json.dumps(condition)}")

        for wallet in rule.target:
            if wallet not in wallet_data:
                logger.warning(f"[WalletWatcher] Wallet {wallet} not found in wallet data")
                continue

            data = wallet_data[wallet]
            current_balance = data.get("balance", 0)
            transactions = data.get("transactions", [])

            # Cache previous balance for change detection
            prev_balance = self.balance_cache.get(wallet, current_balance)
            self.balance_cache[wallet] = current_balance
            balance_change = current_balance - prev_balance

            # Check balance conditions
            if "min_balance" in condition and current_balance < condition["min_balance"]:
                logger.info(f"[WalletWatcher] Balance below minimum: {current_balance} < {condition['min_balance']}")
                matches.append({
                    "wallet": wallet,
                    "condition": "balance_below",
                    "value": current_balance,
                    "threshold": condition["min_balance"]
                })

            # Check significant balance changes
            if abs(balance_change) > 0:  # Any change
                logger.info(f"[WalletWatcher] Balance change detected: {balance_change}")
                matches.append({
                    "wallet": wallet,
                    "condition": "balance_change",
                    "value": balance_change,
                    "old_balance": prev_balance,
                    "new_balance": current_balance
                })

            # Check transactions
            for tx in transactions:
                tx_hash = tx.get("hash")
                if tx_hash not in self.tx_cache:
                    self.tx_cache[tx_hash] = True
                    
                    # Check token transfers
                    if tx.get("type") == "token_transfer":
                        matches.append({
                            "wallet": wallet,
                            "condition": "token_transfer",
                            "token": tx.get("token"),
                            "amount": tx.get("amount"),
                            "direction": tx.get("direction"),
                            "tx_hash": tx_hash
                        })
                    
                    # Check NFT transfers
                    elif tx.get("type") == "nft_transfer":
                        matches.append({
                            "wallet": wallet,
                            "condition": "nft_transfer",
                            "collection": tx.get("collection"),
                            "token_id": tx.get("token_id"),
                            "direction": tx.get("direction"),
                            "tx_hash": tx_hash
                        })

        if matches:
            logger.info(f"[WalletWatcher] Found {len(matches)} matches for rule {rule.rule_id}")
        return matches 