import asyncio
import json
import logging
from typing import Dict, List, Any
from datetime import datetime
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
        self.wallet_types = {}
        self.balance_cache = {}
        self.tx_cache = {}
        
    async def cleanup(self):
        """Cleanup resources"""
        await WalletTrackerFactory.cleanup()

    async def watch_targets(self):
        try:
            watching_targets = set(self.watching_targets)
            logger.info(f"[WalletWatcher] Checking activities for wallets: {list(watching_targets)}")

            # Build target_data from rules
            target_data = {}
            for wallet in watching_targets:
                try:
                    rules = await self.redis.hgetall(f"watch:active:wallet:{wallet}")
                    for rule_json in rules.values():
                        try:
                            rule = Rule.from_dict(json.loads(rule_json) if isinstance(rule_json, str) else rule_json)
                            if rule.target_data:
                                for target_wallet, wallet_info in rule.target_data.items():
                                    if target_wallet not in target_data:
                                        target_data[target_wallet] = wallet_info
                            break
                        except Exception as e:
                            logger.error(f"[WalletWatcher] Error processing rule for wallet {wallet}: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error getting rules for wallet {wallet}: {e}", exc_info=True)

            # Categorize wallets
            evm_wallets = set()
            solana_wallets = set()
            for wallet in watching_targets:
                try:
                    if wallet not in self.wallet_types:
                        wallet_type, is_valid = WalletTrackerFactory.get_wallet_type(wallet)
                        if not is_valid:
                            logger.warning(f"[WalletWatcher] Invalid wallet address: {wallet}")
                            continue
                        self.wallet_types[wallet] = wallet_type
                        logger.info(f"[WalletWatcher] Wallet {wallet} categorized as {wallet_type.value}")

                    if self.wallet_types[wallet] == WalletType.EVM:
                        evm_wallets.add(wallet)
                        logger.info(f"[WalletWatcher] Added {wallet} to EVM wallets")
                    elif self.wallet_types[wallet] == WalletType.SOLANA:
                        solana_wallets.add(wallet)
                        logger.info(f"[WalletWatcher] Added {wallet} to Solana wallets")
                    else:
                        logger.warning(f"[WalletWatcher] Unknown wallet type for {wallet}: {self.wallet_types[wallet]}")
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error validating wallet {wallet}: {e}", exc_info=True)

            logger.info(f"[WalletWatcher] Categorized wallets - EVM: {len(evm_wallets)}, Solana: {len(solana_wallets)}")

            MAX_CONCURRENCY = 10

            async def process_chain(chain, wallets):
                tracker = WalletTrackerFactory.create_tracker(chain)
                sem = asyncio.Semaphore(MAX_CONCURRENCY)
                chain_name = chain.value

                async def process_wallet(wallet):
                    async with sem:
                        try:
                            logger.debug(f"[WalletWatcher] Fetch {chain_name} - {wallet}")
                            data = await tracker.get_wallet_data([wallet])
                            return wallet, data.get(wallet)
                        except Exception as e:
                            logger.error(f"[WalletWatcher] Error getting data for wallet {wallet} on chain {chain_name}: {e}", exc_info=True)
                            return wallet, None

                tasks = [process_wallet(wallet) for wallet in wallets]
                results = await asyncio.gather(*tasks, return_exceptions=False)
                chain_result = {wallet: data for wallet, data in results if data}
                logger.info(f"[WalletWatcher] Done {chain_name}, {len(chain_result)}/{len(wallets)} wallets have data: {list(chain_result.keys())}")
                return chain_name, chain_result

            chain_tasks = []
            if evm_wallets:
                for chain in self.evm_chains:
                    # Đảm bảo mỗi ví EVM sẽ được check trên tất cả các chain EVM
                    chain_tasks.append(process_chain(chain, list(evm_wallets)))
            if solana_wallets:
                chain_tasks.append(process_chain(self.solana_chain, list(solana_wallets)))

            all_wallet_data = {}
            if chain_tasks:
                chain_results = await asyncio.gather(*chain_tasks, return_exceptions=True)
                for res in chain_results:
                    if isinstance(res, Exception):
                        logger.error(f"[WalletWatcher] Error in chain: {res}", exc_info=True)
                        continue
                    chain, data = res
                    if data:
                        all_wallet_data[chain] = data
                        logger.info(f"[WalletWatcher] Collected {len(data)} wallets for chain {chain}")

            if not all_wallet_data:
                logger.warning("[WalletWatcher] No wallet data received from any chain")
                return

            logger.info(f"[WalletWatcher] Received wallet data: {json.dumps(all_wallet_data, cls=MongoJSONEncoder)}")

            # Get all active wallet rules
            active_rules = []
            for wallet in watching_targets:
                try:
                    rules = await self.redis.hgetall(f"watch:active:wallet:{wallet}")
                    for rule_json in rules.values():
                        try:
                            rule = Rule.from_dict(json.loads(rule_json) if isinstance(rule_json, str) else rule_json)
                            active_rules.append(rule)
                        except Exception as e:
                            logger.error(f"[WalletWatcher] Error processing rule for wallet {wallet}: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error getting rules for wallet {wallet}: {e}", exc_info=True)

            # Check conditions for each rule
            if active_rules:
                logger.info(f"[WalletWatcher] Checking {len(active_rules)} rules against wallet data")
                try:
                    await self.check_rules(active_rules, all_wallet_data)
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error checking rules: {e}", exc_info=True)
            else:
                logger.warning("[WalletWatcher] No active rules found for watching wallets")

        except Exception as e:
            logger.error(f"[WalletWatcher] Error watching wallets: {e}", exc_info=True)

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
            MAX_CONCURRENCY = 10
            sem = asyncio.Semaphore(MAX_CONCURRENCY)
            tasks = []

            async def init_wallet(wallet, wallet_type):
                async with sem:
                    try:
                        if wallet_type == WalletType.EVM:
                            for chain in self.evm_chains:
                                tracker = WalletTrackerFactory.create_tracker(chain)
                                await tracker.get_wallet_data([wallet])
                        elif wallet_type == WalletType.SOLANA:
                            tracker = WalletTrackerFactory.create_tracker(self.solana_chain)
                            await tracker.get_wallet_data([wallet])
                    except Exception as e:
                        logger.error(f"[WalletWatcher] Error initializing cache for {wallet}: {e}", exc_info=True)

            for wallet in targets:
                wallet_type, is_valid = WalletTrackerFactory.get_wallet_type(wallet)
                if not is_valid:
                    logger.warning(f"[WalletWatcher] Invalid wallet address: {wallet}")
                    continue
                tasks.append(init_wallet(wallet, wallet_type))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"[WalletWatcher] Error initializing cache: {e}", exc_info=True)
