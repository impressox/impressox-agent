import asyncio
import json
import logging
from typing import Dict, List, Any, Set
import os

from workers.market_monitor.services.base import BaseWatcher
from workers.market_monitor.services.wallet_tracker import WalletTrackerFactory, Chain, WalletType, ActivityType
from workers.market_monitor.shared.models import Rule
from workers.market_monitor.utils.config import get_config
from workers.market_monitor.utils.mongo import MongoJSONEncoder

logger = logging.getLogger(__name__)

class WalletWatcher(BaseWatcher):
    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.watch_type = "wallet"
        self.watch_interval = int(os.getenv("WALLET_WATCH_INTERVAL", 5))
        self.evm_chains = [Chain.ETHEREUM, Chain.BSC, Chain.BASE]
        self.solana_chain = Chain.SOLANA
        self.wallet_types: Dict[str, WalletType] = {}
        self.balance_cache: Dict[str, float] = {}
        self.tx_cache: Dict[str, bool] = {}

    async def watch_targets(self):
        """Watch wallet activities across multiple chains and wallets in parallel."""
        try:
            watching_targets = set(self.watching_targets)
            logger.info(f"[WalletWatcher] Checking activities for wallets: {list(watching_targets)}")

            # 1. Song song lấy rules của từng ví
            rules_per_wallet = await asyncio.gather(
                *(self._get_wallet_rules(wallet) for wallet in watching_targets),
                return_exceptions=True
            )
            target_data = {}
            for wallet, rules in zip(watching_targets, rules_per_wallet):
                if isinstance(rules, Exception):
                    logger.error(f"[WalletWatcher] Error getting rules for wallet {wallet}: {rules}", exc_info=True)
                    continue
                for rule in rules:
                    if rule.target_data:
                        for target_wallet, wallet_info in rule.target_data.items():
                            if target_wallet not in target_data:
                                target_data[target_wallet] = wallet_info

            # 2. Song song xác định loại ví
            categorize_results = await asyncio.gather(
                *(self._get_wallet_type(wallet) for wallet in watching_targets),
                return_exceptions=True
            )
            evm_wallets, solana_wallets = set(), set()
            for wallet, (wallet_type, is_valid) in zip(watching_targets, categorize_results):
                if isinstance(wallet_type, Exception) or not is_valid:
                    logger.warning(f"[WalletWatcher] Invalid wallet address: {wallet}")
                    continue
                self.wallet_types[wallet] = wallet_type
                if wallet_type == WalletType.EVM:
                    evm_wallets.add(wallet)
                elif wallet_type == WalletType.SOLANA:
                    solana_wallets.add(wallet)

            logger.info(f"[WalletWatcher] Categorized wallets - EVM: {len(evm_wallets)}, Solana: {len(solana_wallets)}")

            # 3. Song song từng cặp (chain, wallet) là một task riêng biệt
            async def fetch_wallet(chain, wallet):
                try:
                    tracker = WalletTrackerFactory.create_tracker(chain)
                    result = await tracker.get_wallet_data([wallet])
                    if result and wallet in result:
                        return (chain.value, wallet, result[wallet])
                    return None
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error get_wallet_data: chain={chain}, wallet={wallet}: {e}", exc_info=True)
                    return None

            # Tạo task cho từng cặp chain-wallet độc lập
            tasks = []
            for wallet in evm_wallets:
                for chain in self.evm_chains:
                    tasks.append(fetch_wallet(chain, wallet))
            for wallet in solana_wallets:
                tasks.append(fetch_wallet(self.solana_chain, wallet))

            all_wallet_data: Dict[str, Dict[str, Any]] = {}
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for entry in results:
                    if isinstance(entry, Exception) or not entry:
                        continue
                    chain, wallet, data = entry
                    if chain not in all_wallet_data:
                        all_wallet_data[chain] = {}
                    all_wallet_data[chain][wallet] = data

            if not all_wallet_data:
                logger.warning("[WalletWatcher] No wallet data received from any chain")
                return

            logger.info(f"[WalletWatcher] Received wallet data: {json.dumps(all_wallet_data, cls=MongoJSONEncoder)}")

            # 4. Tổng hợp rules đã lấy ở trên
            all_active_rules = []
            for rules in rules_per_wallet:
                if isinstance(rules, Exception):
                    continue
                all_active_rules.extend(rules)

            if all_active_rules:
                logger.info(f"[WalletWatcher] Checking {len(all_active_rules)} rules against wallet data")
                try:
                    await self.check_rules(all_active_rules, all_wallet_data)
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error checking rules: {e}", exc_info=True)
            else:
                logger.warning("[WalletWatcher] No active rules found for watching wallets")

        except Exception as e:
            logger.error(f"[WalletWatcher] Error watching wallets: {e}", exc_info=True)

    async def _get_wallet_rules(self, wallet: str) -> List[Rule]:
        """Lấy rules cho một ví (async, bắt lỗi sâu)"""
        rules = []
        try:
            rules_data = await self.redis.hgetall(f"watch:active:wallet:{wallet}")
            for rule_json in rules_data.values():
                try:
                    rule = Rule.from_dict(json.loads(rule_json) if isinstance(rule_json, str) else rule_json)
                    rules.append(rule)
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error processing rule for wallet {wallet}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[WalletWatcher] Error getting rules for wallet {wallet}: {e}", exc_info=True)
        return rules

    async def _get_wallet_type(self, wallet: str):
        """Xác định loại ví (EVM/SOLANA), async, không vỡ luồng nếu lỗi"""
        try:
            wallet_type, is_valid = WalletTrackerFactory.get_wallet_type(wallet)
            return wallet_type, is_valid
        except Exception as e:
            logger.error(f"[WalletWatcher] Error categorizing wallet {wallet}: {e}", exc_info=True)
            return None, False

    def evaluate_conditions(self, rule: Rule, wallet_data: Dict) -> List[Dict]:
        matches = []
        condition = rule.condition or {"type": "any"}
        logger.info(f"[WalletWatcher] Evaluating conditions for rule {rule.rule_id}: {json.dumps(condition)}")

        for wallet in rule.target:
            wallet_name = rule.target_data.get(wallet, {}).get("name", wallet)
            for chain_data in wallet_data.values():
                if wallet not in chain_data:
                    continue
                data = chain_data[wallet]
                chain = data.get("chain")
                current_balance = data.get("balance", 0)
                transactions = data.get("transactions", [])

                cache_key = f"{chain}:{wallet}"
                prev_balance = self.balance_cache.get(cache_key, current_balance)
                self.balance_cache[cache_key] = current_balance
                balance_change = current_balance - prev_balance

                tx_matches = {}
                for tx in transactions:
                    tx_hash = tx.get("hash")
                    if not tx_hash or f"{chain}:{tx_hash}" in self.tx_cache:
                        continue
                    self.tx_cache[f"{chain}:{tx_hash}"] = True

                    if tx_hash not in tx_matches:
                        tx_matches[tx_hash] = {
                            'wallet': wallet,
                            'wallet_name': wallet_name,
                            'chain': chain,
                            'hash': tx_hash,
                            'block_number': tx.get('block_number'),
                            'timestamp': tx.get('timestamp'),
                            'transfers': [],
                            'balance_change': balance_change
                        }
                    tx_matches[tx_hash]['transfers'].append(tx)

                for tx_hash, tx_data in tx_matches.items():
                    transfers = tx_data['transfers']
                    balance_change = tx_data['balance_change']
                    token_transfer = next((t for t in transfers if t['type'] == 'token_transfer'), None)

                    if token_transfer:
                        activity_type = token_transfer.get('activity_type')
                        if balance_change < 0 and activity_type == 'token_transfer_in':
                            matches.append({
                                'wallet': wallet,
                                'wallet_name': wallet_name,
                                'chain': chain,
                                'activity_type': 'token_trade',
                                'token_in': 'native',
                                'token_in_name': chain.upper(),
                                'token_in_symbol': self.config.get_native_symbol(chain),
                                'amount_in': abs(balance_change),
                                'formatted_amount_in': str(abs(balance_change)),
                                'token_out': token_transfer.get('token'),
                                'token_out_name': token_transfer.get('token_name'),
                                'token_out_symbol': token_transfer.get('token_symbol'),
                                'amount_out': token_transfer.get('value'),
                                'formatted_amount_out': token_transfer.get('formatted_amount'),
                                'hash': tx_hash,
                                'block_number': tx_data.get('block_number'),
                                'timestamp': tx_data.get('timestamp')
                            })
                        elif balance_change > 0 and activity_type == 'token_transfer_out':
                            matches.append({
                                'wallet': wallet,
                                'wallet_name': wallet_name,
                                'chain': chain,
                                'activity_type': 'token_trade',
                                'token_in': token_transfer.get('token'),
                                'token_in_name': token_transfer.get('token_name'),
                                'token_in_symbol': token_transfer.get('token_symbol'),
                                'amount_in': token_transfer.get('value'),
                                'formatted_amount_in': token_transfer.get('formatted_amount'),
                                'token_out': 'native',
                                'token_out_name': chain.upper(),
                                'token_out_symbol': self.config.get_native_symbol(chain),
                                'amount_out': balance_change,
                                'formatted_amount_out': str(balance_change),
                                'hash': tx_hash,
                                'block_number': tx_data.get('block_number'),
                                'timestamp': tx_data.get('timestamp')
                            })
                        else:
                            matches.append({
                                **token_transfer,
                                'hash': tx_hash,
                                'wallet': wallet,
                                'wallet_name': wallet_name,
                                'chain': chain,
                                'block_number': tx_data.get('block_number'),
                                'timestamp': tx_data.get('timestamp'),
                            })
                    else:
                        for t in transfers:
                            matches.append({
                                **t,
                                'wallet': wallet,
                                'wallet_name': wallet_name,
                                'chain': chain,
                                'hash': tx_hash,
                                'block_number': tx_data.get('block_number'),
                                'timestamp': tx_data.get('timestamp'),
                            })

        return matches

    async def initialize_cache(self, targets: List[str]):
        """Initialize cache for new wallets"""
        try:
            init_tasks = []
            for wallet in targets:
                wallet_type, is_valid = WalletTrackerFactory.get_wallet_type(wallet)
                if not is_valid:
                    logger.warning(f"[WalletWatcher] Invalid wallet address: {wallet}")
                    continue
                if wallet_type == WalletType.EVM:
                    for chain in self.evm_chains:
                        tracker = WalletTrackerFactory.create_tracker(chain)
                        init_tasks.append(tracker.get_wallet_data([wallet]))
                elif wallet_type == WalletType.SOLANA:
                    tracker = WalletTrackerFactory.create_tracker(self.solana_chain)
                    init_tasks.append(tracker.get_wallet_data([wallet]))
            if init_tasks:
                await asyncio.gather(*init_tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"[WalletWatcher] Error initializing cache: {e}", exc_info=True)
