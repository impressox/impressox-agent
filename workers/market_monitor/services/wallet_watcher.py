# services/wallet_watcher.py

import asyncio
import json
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from enum import Enum
from web3 import Web3
from eth_typing import Address
from eth_utils import to_checksum_address, is_address
import base58
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from workers.market_monitor.services.base import BaseWatcher
from workers.market_monitor.shared.models import Rule
from workers.market_monitor.utils.config import get_config
from workers.market_monitor.utils.mongo import MongoJSONEncoder

logger = logging.getLogger(__name__)

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
    def w3(self) -> Web3:
        if self.value == "solana":
            return None
        return Web3(Web3.HTTPProvider(self.rpc_url))

    @property
    def solana_client(self) -> AsyncClient:
        if self.value == "solana":
            return AsyncClient(self.rpc_url, commitment=Confirmed)
        return None

class WalletType(Enum):
    EVM = "evm"
    SOLANA = "solana"

def validate_wallet_address(address: str) -> Tuple[WalletType, bool]:
    """Validate wallet address and determine its type"""
    try:
        # Check if it's a valid Solana address (base58 encoded, 32 bytes)
        decoded = base58.b58decode(address)
        if len(decoded) == 32:
            return WalletType.SOLANA, True
    except:
        pass

    # Check if it's a valid EVM address
    if is_address(address):
        return WalletType.EVM, True

    return None, False

class ActivityType(Enum):
    NATIVE_TRANSFER_IN = "native_transfer_in"
    NATIVE_TRANSFER_OUT = "native_transfer_out"
    TOKEN_TRANSFER_IN = "token_transfer_in"
    TOKEN_TRADE = "token_trade"
    NFT_TRANSFER_IN = "nft_transfer_in"
    NFT_TRADE = "nft_trade"

# ERC20 ABI for token transfers
ERC20_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]

# ERC721 ABI for NFT transfers
ERC721_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": True, "name": "tokenId", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]

# ERC1155 ABI for NFT transfers
ERC1155_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "id", "type": "uint256"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "TransferSingle",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "ids", "type": "uint256[]"},
            {"indexed": False, "name": "values", "type": "uint256[]"}
        ],
        "name": "TransferBatch",
        "type": "event"
    }
]

class WalletWatcher(BaseWatcher):
    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.balance_cache = {}  # Cache wallet balances per chain
        self.tx_cache = {}  # Cache recent transactions per chain
        self.watch_type = "wallet"
        self.watch_interval = 10  # Check more frequently for wallets
        self.evm_chains = [Chain.ETHEREUM, Chain.BSC, Chain.BASE]
        self.solana_chain = Chain.SOLANA
        self.block_cache = {}  # Cache latest block numbers per chain
        self.wallet_types = {}  # Cache wallet types
        
        # Pre-compute event topics
        self.token_transfer_topic = '0x' + Web3.keccak(text='Transfer(address,address,uint256)').hex()
        self.erc1155_single_topic = '0x' + Web3.keccak(text='TransferSingle(address,address,address,uint256,uint256)').hex()
        self.erc1155_batch_topic = '0x' + Web3.keccak(text='TransferBatch(address,address,address,uint256[],uint256[])').hex()

    async def watch_targets(self):
        """Watch wallet activities across multiple chains"""
        try:
            logger.info(f"[WalletWatcher] Checking activities for wallets: {list(self.watching_targets)}")
            
            # Get target_data from active rules
            target_data = {}
            for wallet in self.watching_targets:
                try:
                    rules = await self.redis.hgetall(f"watch:active:wallet:{wallet}")
                    for rule_json in rules.values():
                        try:
                            # Handle both string and dict data types from Redis
                            if isinstance(rule_json, str):
                                rule = Rule.from_dict(json.loads(rule_json))
                            else:
                                rule = Rule.from_dict(rule_json)
                            if rule.target_data:
                                target_data.update(rule.target_data)
                            break
                        except Exception as e:
                            logger.error(f"[WalletWatcher] Error processing rule for wallet {wallet}: {e}", exc_info=True)
                            continue
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error getting rules for wallet {wallet}: {e}", exc_info=True)
                    continue

            # Validate and categorize wallets
            evm_wallets = set()
            solana_wallets = set()
            
            for wallet in self.watching_targets:
                try:
                    if wallet not in self.wallet_types:
                        wallet_type, is_valid = validate_wallet_address(wallet)
                        if not is_valid:
                            logger.warning(f"[WalletWatcher] Invalid wallet address: {wallet}")
                            continue
                        self.wallet_types[wallet] = wallet_type
                    
                    if self.wallet_types[wallet] == WalletType.EVM:
                        evm_wallets.add(wallet)
                    else:
                        solana_wallets.add(wallet)
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error validating wallet {wallet}: {e}", exc_info=True)
                    continue

            # Get wallet data for each chain in parallel
            all_wallet_data = {}
            tasks = []
            
            # Add tasks for EVM chains
            if evm_wallets:
                for chain in self.evm_chains:
                    tasks.append(self.get_wallet_data(
                        list(evm_wallets), 
                        chain,
                        target_data
                    ))

            # Add task for Solana chain
            if solana_wallets:
                tasks.append(self.get_wallet_data(
                    list(solana_wallets),
                    self.solana_chain,
                    target_data
                ))

            # Run all tasks in parallel
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"[WalletWatcher] Error getting wallet data: {result}", exc_info=True)
                        continue
                    
                    if result:
                        if i < len(self.evm_chains):
                            chain = self.evm_chains[i]
                            all_wallet_data[chain.value] = result
                        else:
                            all_wallet_data[self.solana_chain.value] = result

            if not all_wallet_data:
                logger.warning("[WalletWatcher] No wallet data received from any chain")
                return

            logger.info(f"[WalletWatcher] Received wallet data: {json.dumps(all_wallet_data, cls=MongoJSONEncoder)}")

            # Get all active wallet rules
            active_rules = []
            for wallet in self.watching_targets:
                try:
                    rules = await self.redis.hgetall(f"watch:active:wallet:{wallet}")
                    for rule_json in rules.values():
                        try:
                            # Handle both string and dict data types from Redis
                            if isinstance(rule_json, str):
                                rule = Rule.from_dict(json.loads(rule_json))
                            else:
                                rule = Rule.from_dict(rule_json)
                            active_rules.append(rule)
                        except Exception as e:
                            logger.error(f"[WalletWatcher] Error processing rule for wallet {wallet}: {e}", exc_info=True)
                            continue
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error getting rules for wallet {wallet}: {e}", exc_info=True)
                    continue

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

    async def get_wallet_data(self, wallets: List[str], chain: Chain, target_data: Dict = None) -> Dict:
        """Get current wallet data from blockchain using Web3 or Solana client"""
        try:
            logger.info(f"[WalletWatcher] Fetching {chain.value} data for wallets: {wallets}")
            
            if chain == Chain.SOLANA:
                return await self._get_solana_wallet_data(wallets)
            
            w3 = chain.w3
            if not w3.is_connected():
                logger.error(f"[WalletWatcher] Failed to connect to {chain.value} RPC")
                return {}

            result = {}
            current_block = w3.eth.block_number
            from_block = self.block_cache.get(chain.value, current_block - 100)  # Default to last 100 blocks
            
            for wallet in wallets:
                try:
                    wallet = to_checksum_address(wallet)
                    
                    # Get native token balance
                    balance = w3.eth.get_balance(wallet)
                    
                    # Get logs for each event type separately
                    all_logs = []
                    
                    # Helper function to get logs using direct RPC call
                    def get_logs_direct(filter_params):
                        try:
                            response = w3.provider.make_request(
                                'eth_getLogs',
                                [filter_params]
                            )
                            if response and 'result' in response:
                                return response['result']
                            return []
                        except Exception as e:
                            logger.error(f"[WalletWatcher] RPC call error: {e}", exc_info=True)
                            return []

                    # Get ERC20 Transfer events
                    erc20_filter = {
                        'fromBlock': hex(from_block),
                        'toBlock': hex(current_block),
                        'topics': [[self.token_transfer_topic]],
                        'address': None
                    }
                    erc20_logs = get_logs_direct(erc20_filter)
                    if erc20_logs:
                        all_logs.extend(erc20_logs)

                    # Get ERC1155 Single Transfer events
                    erc1155_single_filter = {
                        'fromBlock': hex(from_block),
                        'toBlock': hex(current_block),
                        'topics': [[self.erc1155_single_topic]],
                        'address': None
                    }
                    erc1155_single_logs = get_logs_direct(erc1155_single_filter)
                    if erc1155_single_logs:
                        all_logs.extend(erc1155_single_logs)

                    # Get ERC1155 Batch Transfer events
                    erc1155_batch_filter = {
                        'fromBlock': hex(from_block),
                        'toBlock': hex(current_block),
                        'topics': [[self.erc1155_batch_topic]],
                        'address': None
                    }
                    erc1155_batch_logs = get_logs_direct(erc1155_batch_filter)
                    if erc1155_batch_logs:
                        all_logs.extend(erc1155_batch_logs)

                    # Filter logs for the specific wallet
                    filtered_logs = []
                    for log in all_logs:
                        try:
                            if len(log['topics']) >= 3:
                                from_address = '0x' + log['topics'][1][-40:]
                                to_address = '0x' + log['topics'][2][-40:]
                                if wallet.lower() in [from_address.lower(), to_address.lower()]:
                                    filtered_logs.append(log)
                        except Exception as e:
                            logger.error(f"[WalletWatcher] Error processing log topics: {e}", exc_info=True)
                            continue

                    logs = filtered_logs
                    
                    # Process logs
                    transactions = self._process_wallet_logs(logs, wallet)
                    
                    result[wallet] = {
                        'chain': chain.value,
                        'balance': w3.from_wei(balance, 'ether'),
                        'transactions': transactions,
                        'last_updated': datetime.utcnow().isoformat()
                    }
                except Exception as e:
                    logger.error(f"[WalletWatcher] Error processing wallet {wallet}: {e}", exc_info=True)
                    continue
            
            # Update block cache
            self.block_cache[chain.value] = current_block
            
            return result
            
        except Exception as e:
            logger.error(f"[WalletWatcher] Error fetching {chain.value} wallet data: {e}", exc_info=True)
            return {}

    async def _get_solana_wallet_data(self, wallets: List[str]) -> Dict:
        """Get wallet data from Solana blockchain"""
        try:
            client = Chain.SOLANA.solana_client
            result = {}
            
            for wallet in wallets:
                try:
                    # Get SOL balance
                    balance = await client.get_balance(wallet)
                    if balance.value:
                        sol_balance = balance.value / 1e9  # Convert lamports to SOL
                    else:
                        sol_balance = 0

                    # Get recent transactions
                    signatures = await client.get_signatures_for_address(wallet, limit=10)
                    transactions = []

                    for sig_info in signatures.value:
                        tx_hash = sig_info.signature
                        if tx_hash not in self.tx_cache:
                            self.tx_cache[tx_hash] = True
                            
                            # Get transaction details
                            tx = await client.get_transaction(tx_hash)
                            if tx.value:
                                tx_data = tx.value
                                
                                # Process transaction
                                tx_info = {
                                    'type': 'solana_transfer',
                                    'hash': tx_hash,
                                    'block_number': tx_data.slot,
                                    'timestamp': datetime.fromtimestamp(tx_data.block_time).isoformat() if tx_data.block_time else None,
                                    'fee': tx_data.meta.fee / 1e9 if tx_data.meta and tx_data.meta.fee else 0,
                                }

                                # Check if it's a token transfer
                                if tx_data.meta and tx_data.meta.post_token_balances:
                                    for balance in tx_data.meta.post_token_balances:
                                        if balance.owner == wallet:
                                            tx_info.update({
                                                'type': 'token_transfer',
                                                'token': balance.mint,
                                                'amount': balance.ui_token_amount.ui_amount,
                                                'decimals': balance.ui_token_amount.decimals
                                            })

                                transactions.append(tx_info)

                    result[wallet] = {
                        'chain': 'solana',
                        'balance': sol_balance,
                        'transactions': transactions,
                        'last_updated': datetime.utcnow().isoformat()
                    }

                except Exception as e:
                    logger.error(f"[WalletWatcher] Error processing Solana wallet {wallet}: {e}")
                    continue

            return result

        except Exception as e:
            logger.error(f"[WalletWatcher] Error fetching Solana wallet data: {e}", exc_info=True)
            return {}

    def evaluate_conditions(self, rule: Rule, wallet_data: Dict) -> List[Dict]:
        """Evaluate rule conditions against wallet data across all chains"""
        matches = []
        condition = rule.condition or {"type": "any"}
        logger.info(f"[WalletWatcher] Evaluating conditions for rule {rule.rule_id}: {json.dumps(condition)}")

        for wallet in rule.target:
            for chain_data in wallet_data.values():
                if wallet not in chain_data:
                    continue

                data = chain_data[wallet]
                chain = data.get("chain")
                current_balance = data.get("balance", 0)
                transactions = data.get("transactions", [])

                # Cache previous balance for change detection
                cache_key = f"{chain}:{wallet}"
                prev_balance = self.balance_cache.get(cache_key, current_balance)
                self.balance_cache[cache_key] = current_balance
                balance_change = current_balance - prev_balance

                # Check native token transfers
                if balance_change > 0:
                    matches.append({
                        "wallet": wallet,
                        "chain": chain,
                        "activity_type": ActivityType.NATIVE_TRANSFER_IN.value,
                        "amount": balance_change,
                        "old_balance": prev_balance,
                        "new_balance": current_balance,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                elif balance_change < 0:
                    matches.append({
                        "wallet": wallet,
                        "chain": chain,
                        "activity_type": ActivityType.NATIVE_TRANSFER_OUT.value,
                        "amount": abs(balance_change),
                        "old_balance": prev_balance,
                        "new_balance": current_balance,
                        "timestamp": datetime.utcnow().isoformat()
                    })

                # Process transactions
                for tx in transactions:
                    tx_hash = tx['hash']
                    cache_key = f"{chain}:{tx_hash}"
                    
                    if cache_key not in self.tx_cache:
                        self.tx_cache[cache_key] = True
                        
                        if tx['type'] == 'token_transfer':
                            if tx['to'].lower() == wallet.lower():  # Only track incoming transfers
                                matches.append({
                                    "wallet": wallet,
                                    "chain": chain,
                                    "activity_type": ActivityType.TOKEN_TRANSFER_IN.value,
                                    "token": tx['token'],
                                    "amount": tx['value'],
                                    "tx_hash": tx_hash,
                                    "block_number": tx['block_number'],
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                        
                        elif tx['type'] == 'nft_transfer':
                            if tx['to'].lower() == wallet.lower():  # Only track incoming transfers
                                matches.append({
                                    "wallet": wallet,
                                    "chain": chain,
                                    "activity_type": ActivityType.NFT_TRANSFER_IN.value,
                                    "standard": tx['standard'],
                                    "collection": tx['collection'],
                                    "token_id": tx['token_id'],
                                    "amount": tx.get('amount', 1),  # Default to 1 for ERC721
                                    "tx_hash": tx_hash,
                                    "block_number": tx['block_number'],
                                    "timestamp": datetime.utcnow().isoformat()
                                })

        if matches:
            logger.info(f"[WalletWatcher] Found {len(matches)} matches for rule {rule.rule_id}")
        return matches

    def _process_wallet_logs(self, logs: List[Dict], wallet: str) -> List[Dict]:
        """Process all logs for a wallet"""
        transactions = []
        for log in logs:
            try:
                # Skip if already processed
                tx_hash = log['transactionHash']  # Already hex string from RPC
                if tx_hash in self.tx_cache:
                    continue
                    
                # Process based on topic
                if log['topics'][0] == self.token_transfer_topic:
                    tx = self._process_token_transfer(log, wallet)
                    if tx:
                        transactions.append(tx)
                        self.tx_cache[tx_hash] = True
                elif log['topics'][0] in [self.erc1155_single_topic, self.erc1155_batch_topic]:
                    tx = self._process_erc1155_transfer(log, wallet)
                    if tx:
                        transactions.append(tx)
                        self.tx_cache[tx_hash] = True
            except Exception as e:
                logger.error(f"[WalletWatcher] Error processing log: {e}", exc_info=True)
                continue
        return transactions

    def _process_token_transfer(self, log: Dict, wallet: str) -> Optional[Dict]:
        """Process ERC20 token transfer log"""
        try:
            if len(log['topics']) < 3:
                return None
                
            from_address = '0x' + log['topics'][1][-40:]  # Already hex string
            to_address = '0x' + log['topics'][2][-40:]    # Already hex string
            
            # Skip if wallet is not involved
            if wallet.lower() not in [from_address.lower(), to_address.lower()]:
                return None
                
            # Convert data to hex string if it's bytes
            data = log['data']
            if not data.startswith('0x'):
                data = '0x' + data
                
            # Skip if data is just '0x'
            if data == '0x':
                return None
                
            value = int(data, 16)
            
            return {
                'type': 'token_transfer',
                'hash': log['transactionHash'],  # Already hex string
                'token': log['address'],
                'from': from_address,
                'to': to_address,
                'value': value,
                'block_number': int(log['blockNumber'], 16)  # Convert hex to int
            }
        except Exception as e:
            logger.error(f"[WalletWatcher] Error processing token transfer: {e}", exc_info=True)
            return None

    def _process_erc1155_transfer(self, log: Dict, wallet: str) -> Optional[Dict]:
        """Process ERC1155 transfer log"""
        try:
            if len(log['topics']) < 4:
                return None
                
            operator = '0x' + log['topics'][1][-40:]  # Already hex string
            from_address = '0x' + log['topics'][2][-40:]  # Already hex string
            to_address = '0x' + log['topics'][3][-40:]  # Already hex string
            
            # Skip if wallet is not involved
            if wallet.lower() not in [from_address.lower(), to_address.lower()]:
                return None
                
            # Convert data to hex string if it's bytes
            data = log['data']
            if not data.startswith('0x'):
                data = '0x' + data
                
            # Skip if data is just '0x'
            if data == '0x':
                return None
                
            data = data[2:]  # Remove '0x'
            
            if log['topics'][0] == self.erc1155_single_topic:
                # Single transfer
                id_value = int(data[:64], 16)
                amount = int(data[64:], 16)
                
                return {
                    'type': 'nft_transfer',
                    'standard': 'ERC1155',
                    'hash': log['transactionHash'],  # Already hex string
                    'collection': log['address'],
                    'from': from_address,
                    'to': to_address,
                    'token_id': id_value,
                    'amount': amount,
                    'block_number': int(log['blockNumber'], 16)  # Convert hex to int
                }
            else:
                # Batch transfer
                data = data[64:]  # Skip ids array length
                ids_count = int(data[:64], 16)
                data = data[64:]  # Skip values array length
                values_count = int(data[:64], 16)
                data = data[64:]
                
                # Process first item only to avoid complexity
                if ids_count > 0 and values_count > 0:
                    token_id = int(data[:64], 16)
                    amount = int(data[64:128], 16)
                    
                    return {
                        'type': 'nft_transfer',
                        'standard': 'ERC1155',
                        'hash': log['transactionHash'],  # Already hex string
                        'collection': log['address'],
                        'from': from_address,
                        'to': to_address,
                        'token_id': token_id,
                        'amount': amount,
                        'block_number': int(log['blockNumber'], 16)  # Convert hex to int
                    }
        except Exception as e:
            logger.error(f"[WalletWatcher] Error processing ERC1155 transfer: {e}", exc_info=True)
            return None 