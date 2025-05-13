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
import time

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
        self.watch_interval = 1  # Check more frequently for wallets
        self.evm_chains = [Chain.ETHEREUM, Chain.BSC, Chain.BASE]
        self.solana_chain = Chain.SOLANA
        self.block_cache = {}  # Cache latest block numbers per chain
        self.wallet_types = {}  # Cache wallet types
        self.token_cache = {}  # Cache token metadata
        
        # Pre-compute event topics
        self.token_transfer_topic = '0x' + Web3.keccak(text='Transfer(address,address,uint256)').hex()
        self.erc1155_single_topic = '0x' + Web3.keccak(text='TransferSingle(address,address,address,uint256,uint256)').hex()
        self.erc1155_batch_topic = '0x' + Web3.keccak(text='TransferBatch(address,address,address,uint256[],uint256[])').hex()
        
        # Common DEX router addresses
        self.dex_routers = {
            'ethereum': [
                '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',  # Uniswap V2
                '0xE592427A0AEce92De3Edee1F18E0157C05861564',  # Uniswap V3
                '0x1111111254EEB25477B68fb85Ed929f73A960582',  # 1inch
                '0xDef1C0ded9bec7F1a1670819833240f027b25EfF'   # 0x Protocol
            ],
            'bsc': [
                '0x10ED43C718714eb63d5aA57B78B54704E256024E',  # PancakeSwap V2
                '0x13f4EA83D0bd40E75C8222255bc855a974568Dd4',  # PancakeSwap V3
                '0x1111111254EEB25477B68fb85Ed929f73A960582'   # 1inch
            ],
            'base': [
                '0x327Df1E6de05895d2ab08513aaDD9313Fe505D86',  # BaseSwap
                '0x1111111254EEB25477B68fb85Ed929f73A960582'   # 1inch
            ]
        }

        # ERC20 ABI for token metadata
        self.erc20_abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "name",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]

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
                    transactions = self._process_wallet_logs(logs, wallet, chain.value)
                    
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

                # Process transactions
                tx_matches = {}  # Group transactions by hash
                for tx in transactions:
                    tx_hash = tx.get('hash')
                    if not tx_hash:
                        continue
                        
                    cache_key = f"{chain}:{tx_hash}"
                    if cache_key in self.tx_cache:
                        continue
                        
                    self.tx_cache[cache_key] = True
                    
                    if tx_hash not in tx_matches:
                        tx_matches[tx_hash] = {
                            'wallet': wallet,
                            'chain': chain,
                            'hash': tx_hash,
                            'block_number': tx.get('block_number'),
                            'timestamp': datetime.utcnow().isoformat(),
                            'transfers': [],
                            'balance_change': balance_change  # Add balance change to transaction data
                        }
                    
                    if tx['type'] == 'token_transfer':
                        tx_matches[tx_hash]['transfers'].append({
                            'type': 'token_transfer',
                            'activity_type': tx.get('activity_type', 'token_transfer_in'),
                            'token': tx.get('token'),
                            'token_name': tx.get('token_name'),
                            'token_symbol': tx.get('token_symbol'),
                            'amount': tx.get('value'),
                            'formatted_amount': tx.get('formatted_amount'),
                            'from': tx.get('from'),
                            'to': tx.get('to')
                        })
                    elif tx['type'] == 'native_transfer':
                        tx_matches[tx_hash]['transfers'].append({
                            'type': 'native_transfer',
                            'activity_type': tx.get('activity_type'),
                            'amount': tx.get('value'),
                            'formatted_amount': tx.get('formatted_amount'),
                            'from': tx.get('from'),
                            'to': tx.get('to')
                        })
                    elif tx['type'] == 'token_trade':
                        matches.append({
                            'wallet': wallet,
                            'chain': chain,
                            'activity_type': 'token_trade',
                            'token_in': tx.get('token_in'),
                            'token_in_name': tx.get('token_in_name'),
                            'token_in_symbol': tx.get('token_in_symbol'),
                            'amount_in': tx.get('amount_in'),
                            'formatted_amount_in': tx.get('formatted_amount_in'),
                            'token_out': tx.get('token_out'),
                            'token_out_name': tx.get('token_out_name'),
                            'token_out_symbol': tx.get('token_out_symbol'),
                            'amount_out': tx.get('amount_out'),
                            'formatted_amount_out': tx.get('formatted_amount_out'),
                            'hash': tx_hash,
                            'block_number': tx.get('block_number'),
                            'timestamp': datetime.utcnow().isoformat()
                        })

                # Process grouped transactions
                for tx_hash, tx_data in tx_matches.items():
                    transfers = tx_data['transfers']
                    balance_change = tx_data['balance_change']
                    
                    # Check for token purchase/sell
                    token_transfer = None
                    
                    for transfer in transfers:
                        if transfer['type'] == 'token_transfer':
                            token_transfer = transfer
                            break
                    
                    if token_transfer:
                        if balance_change < 0 and token_transfer['activity_type'] == 'token_transfer_in':
                            # This is a token purchase (native token sent, token received)
                            matches.append({
                                'wallet': tx_data['wallet'],
                                'chain': tx_data['chain'],
                                'activity_type': 'token_trade',
                                'token_in': 'native',
                                'token_in_name': tx_data['chain'].upper(),
                                'token_in_symbol': self.config.get_native_symbol(tx_data['chain']),
                                'amount_in': abs(balance_change),
                                'formatted_amount_in': str(abs(balance_change)),
                                'token_out': token_transfer['token'],
                                'token_out_name': token_transfer['token_name'],
                                'token_out_symbol': token_transfer['token_symbol'],
                                'amount_out': token_transfer['amount'],
                                'formatted_amount_out': token_transfer['formatted_amount'],
                                'hash': tx_hash,
                                'block_number': tx_data['block_number'],
                                'timestamp': tx_data['timestamp']
                            })
                        elif balance_change > 0 and token_transfer['activity_type'] == 'token_transfer_out':
                            # This is a token sell (token sent, native token received)
                            matches.append({
                                'wallet': tx_data['wallet'],
                                'chain': tx_data['chain'],
                                'activity_type': 'token_trade',
                                'token_in': token_transfer['token'],
                                'token_in_name': token_transfer['token_name'],
                                'token_in_symbol': token_transfer['token_symbol'],
                                'amount_in': token_transfer['amount'],
                                'formatted_amount_in': token_transfer['formatted_amount'],
                                'token_out': 'native',
                                'token_out_name': tx_data['chain'].upper(),
                                'token_out_symbol': self.config.get_native_symbol(tx_data['chain']),
                                'amount_out': balance_change,
                                'formatted_amount_out': str(balance_change),
                                'hash': tx_hash,
                                'block_number': tx_data['block_number'],
                                'timestamp': tx_data['timestamp']
                            })
                        else:
                            # Regular token transfer
                            matches.append({
                                'wallet': tx_data['wallet'],
                                'chain': tx_data['chain'],
                                'activity_type': token_transfer['activity_type'],
                                'token': token_transfer['token'],
                                'token_name': token_transfer['token_name'],
                                'token_symbol': token_transfer['token_symbol'],
                                'amount': token_transfer['amount'],
                                'formatted_amount': token_transfer['formatted_amount'],
                                'from': token_transfer['from'],
                                'to': token_transfer['to'],
                                'hash': tx_hash,
                                'block_number': tx_data['block_number'],
                                'timestamp': tx_data['timestamp']
                            })
                    else:
                        # Add native transfers
                        for transfer in transfers:
                            if transfer['type'] == 'native_transfer':
                                matches.append({
                                    'wallet': tx_data['wallet'],
                                    'chain': tx_data['chain'],
                                    'activity_type': transfer['activity_type'],
                                    'amount': transfer['amount'],
                                    'formatted_amount': transfer['formatted_amount'],
                                    'from': transfer['from'],
                                    'to': transfer['to'],
                                    'hash': tx_hash,
                                    'block_number': tx_data['block_number'],
                                    'timestamp': tx_data['timestamp']
                                })

        if matches:
            logger.info(f"[WalletWatcher] Found {len(matches)} matches for rule {rule.rule_id}")
        return matches

    def _process_wallet_logs(self, logs: List[Dict], wallet: str, chain: str) -> List[Dict]:
        """Process all logs for a wallet"""
        transactions = []
        tx_logs = {}  # Group logs by transaction hash
        
        # Group logs by transaction hash
        for log in logs:
            try:
                tx_hash = log['transactionHash']
                if tx_hash not in tx_logs:
                    tx_logs[tx_hash] = []
                tx_logs[tx_hash].append(log)
            except Exception as e:
                logger.error(f"[WalletWatcher] Error grouping logs: {e}", exc_info=True)
                continue

        # Process each transaction's logs
        for tx_hash, tx_logs_list in tx_logs.items():
            try:
                if tx_hash in self.tx_cache:
                    continue

                # Check if this is a DEX swap
                is_swap = False
                token_in = None
                token_out = None
                amount_in = None
                amount_out = None
                native_sent = None
                token_received = None
                
                # Check if transaction involves a DEX router
                for log in tx_logs_list:
                    if log['address'].lower() in [r.lower() for r in self.dex_routers.get(chain, [])]:
                        is_swap = True
                        break

                if is_swap:
                    # Process swap logs
                    for log in tx_logs_list:
                        if log['topics'][0] == self.token_transfer_topic:
                            from_address = '0x' + log['topics'][1][-40:]
                            to_address = '0x' + log['topics'][2][-40:]
                            
                            # Get token metadata
                            w3 = Web3(Web3.HTTPProvider(self.config.get_rpc_url(chain)))
                            token_metadata = self._get_token_metadata(w3, log['address'], chain)
                            
                            # Convert data to hex string if needed
                            data = log['data']
                            if not data.startswith('0x'):
                                data = '0x' + data
                            value = int(data, 16)
                            formatted_amount = self._format_token_amount(value, token_metadata['decimals'])
                            
                            # Determine if this is input or output token
                            if from_address.lower() == wallet.lower():
                                # Token being sold
                                token_in = {
                                    'address': log['address'],
                                    'name': token_metadata['name'],
                                    'symbol': token_metadata['symbol'],
                                    'amount': value,
                                    'formatted_amount': formatted_amount
                                }
                            elif to_address.lower() == wallet.lower():
                                # Token being bought
                                token_out = {
                                    'address': log['address'],
                                    'name': token_metadata['name'],
                                    'symbol': token_metadata['symbol'],
                                    'amount': value,
                                    'formatted_amount': formatted_amount
                                }
                    
                    # Check if this is a token to native swap
                    if token_in and not token_out:
                        # This is a token to native swap
                        transactions.append({
                            'type': 'token_trade',
                            'hash': tx_hash,
                            'wallet': wallet,
                            'token_in': token_in['address'],
                            'token_in_name': token_in['name'],
                            'token_in_symbol': token_in['symbol'],
                            'amount_in': token_in['amount'],
                            'formatted_amount_in': token_in['formatted_amount'],
                            'token_out': 'native',
                            'token_out_name': chain.upper(),
                            'token_out_symbol': self.config.get_native_symbol(chain),
                            'block_number': int(tx_logs_list[0]['blockNumber'], 16),
                            'chain': chain
                        })
                        self.tx_cache[tx_hash] = True
                    elif not token_in and token_out:
                        # This is a native to token swap
                        transactions.append({
                            'type': 'token_trade',
                            'hash': tx_hash,
                            'wallet': wallet,
                            'token_in': 'native',
                            'token_in_name': chain.upper(),
                            'token_in_symbol': self.config.get_native_symbol(chain),
                            'amount_in': native_sent['amount'] if native_sent else 0,
                            'formatted_amount_in': native_sent['formatted_amount'] if native_sent else '0',
                            'token_out': token_out['address'],
                            'token_out_name': token_out['name'],
                            'token_out_symbol': token_out['symbol'],
                            'amount_out': token_out['amount'],
                            'formatted_amount_out': token_out['formatted_amount'],
                            'block_number': int(tx_logs_list[0]['blockNumber'], 16),
                            'chain': chain
                        })
                        self.tx_cache[tx_hash] = True
                else:
                    # Process regular token transfers
                    native_transfer = None
                    token_transfer = None
                    
                    for log in tx_logs_list:
                        if log['topics'][0] == self.token_transfer_topic:
                            tx = self._process_token_transfer(log, wallet, chain)
                            if tx:
                                if tx['activity_type'] == 'token_transfer_in':
                                    token_transfer = tx
                                else:
                                    transactions.append(tx)
                        elif log['topics'][0] in [self.erc1155_single_topic, self.erc1155_batch_topic]:
                            tx = self._process_erc1155_transfer(log, wallet)
                            if tx:
                                transactions.append(tx)
                    
                    # Check if this is a native token transfer
                    for log in tx_logs_list:
                        if 'value' in log and log['value'] != '0x0':
                            from_address = '0x' + log['topics'][1][-40:] if len(log['topics']) > 1 else None
                            to_address = '0x' + log['topics'][2][-40:] if len(log['topics']) > 2 else None
                            
                            if from_address and to_address:
                                if from_address.lower() == wallet.lower():
                                    native_transfer = {
                                        'type': 'native_transfer',
                                        'activity_type': 'native_transfer_out',
                                        'hash': log['transactionHash'],
                                        'from': from_address,
                                        'to': to_address,
                                        'value': int(log['value'], 16),
                                        'formatted_amount': self._format_token_amount(int(log['value'], 16), 18),
                                        'block_number': int(log['blockNumber'], 16),
                                        'chain': chain,
                                        'token_symbol': self.config.get_native_symbol(chain)
                                    }
                    
                    # If we have both native transfer out and token transfer in, it's likely a purchase
                    if native_transfer and token_transfer and native_transfer['activity_type'] == 'native_transfer_out' and token_transfer['activity_type'] == 'token_transfer_in':
                        transactions.append({
                            'type': 'token_trade',
                            'hash': tx_hash,
                            'wallet': wallet,
                            'token_in': 'native',
                            'token_in_name': chain.upper(),
                            'token_in_symbol': self.config.get_native_symbol(chain),
                            'amount_in': native_transfer['value'],
                            'formatted_amount_in': native_transfer['formatted_amount'],
                            'token_out': token_transfer['token'],
                            'token_out_name': token_transfer['token_name'],
                            'token_out_symbol': token_transfer['token_symbol'],
                            'amount_out': token_transfer['value'],
                            'formatted_amount_out': token_transfer['formatted_amount'],
                            'block_number': int(tx_logs_list[0]['blockNumber'], 16),
                            'chain': chain
                        })
                        self.tx_cache[tx_hash] = True
                    else:
                        # Add individual transfers if not part of a trade
                        if native_transfer:
                            transactions.append(native_transfer)
                        if token_transfer:
                            transactions.append(token_transfer)

            except Exception as e:
                logger.error(f"[WalletWatcher] Error processing transaction logs: {e}", exc_info=True)
                continue

        return transactions

    def _get_token_metadata(self, w3: Web3, token_address: str, chain: str) -> Dict:
        """Get token metadata (name, symbol, decimals)"""
        try:
            # Convert to checksum address
            token_address = Web3.to_checksum_address(token_address)
            logger.info(f"[WalletWatcher] Getting metadata for {token_address} on {chain}")
            # Check cache first with chain-specific key
            cache_key = f"{chain}:{token_address}"
            if cache_key in self.token_cache:
                logger.info(f"[WalletWatcher] Using cached metadata for {token_address} on {chain}")
                return self.token_cache[cache_key]

            # Ensure we're using the correct chain's RPC
            rpc_url = self.config.get_rpc_url(chain)
            if w3.provider.endpoint_uri != rpc_url:
                logger.info(f"[WalletWatcher] Switching to {chain} RPC for {token_address}")
                w3 = Web3(Web3.HTTPProvider(rpc_url))

            # Create contract instance
            contract = w3.eth.contract(address=token_address, abi=self.erc20_abi)
            
            # Get metadata with retries
            max_retries = 3
            retry_delay = 1
            
            for attempt in range(max_retries):
                try:
                    # Get name
                    try:
                        name = contract.functions.name().call()
                        if not name or name == "Unknown":
                            name = f"Token-{token_address[:8]}"
                    except Exception as e:
                        logger.warning(f"[WalletWatcher] Error getting name for {token_address} on {chain}: {e}")
                        name = f"Token-{token_address[:8]}"
                    
                    # Get symbol
                    try:
                        symbol = contract.functions.symbol().call()
                        if not symbol or symbol == "Unknown":
                            symbol = f"TKN-{token_address[:4]}"
                    except Exception as e:
                        logger.warning(f"[WalletWatcher] Error getting symbol for {token_address} on {chain}: {e}")
                        symbol = f"TKN-{token_address[:4]}"
                    
                    # Get decimals
                    try:
                        decimals = contract.functions.decimals().call()
                        if decimals is None:
                            decimals = 18
                    except Exception as e:
                        logger.warning(f"[WalletWatcher] Error getting decimals for {token_address} on {chain}: {e}")
                        decimals = 18
                    
                    metadata = {
                        "name": name,
                        "symbol": symbol,
                        "decimals": decimals
                    }
                    
                    # Cache the result with chain-specific key
                    self.token_cache[cache_key] = metadata
                    logger.info(f"[WalletWatcher] Cached metadata for {token_address} on {chain}: {metadata}")
                    return metadata
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"[WalletWatcher] Retry {attempt + 1}/{max_retries} for {token_address} on {chain}: {e}")
                        time.sleep(retry_delay)
                    else:
                        raise
            
            # If all retries failed, return default metadata
            metadata = {
                "name": f"Token-{token_address[:8]}",
                "symbol": f"TKN-{token_address[:4]}",
                "decimals": 18
            }
            
            # Cache the default metadata
            self.token_cache[cache_key] = metadata
            logger.warning(f"[WalletWatcher] Using default metadata for {token_address} on {chain}")
            return metadata
            
        except Exception as e:
            logger.error(f"[WalletWatcher] Error getting token metadata for {token_address} on {chain}: {e}", exc_info=True)
            # Return default metadata on error
            return {
                "name": f"Token-{token_address[:8]}",
                "symbol": f"TKN-{token_address[:4]}",
                "decimals": 18
            }

    def _format_token_amount(self, amount: int, decimals: int) -> str:
        """Format token amount with proper decimals"""
        try:
            if decimals == 0:
                return str(amount)
            amount_str = str(amount).zfill(decimals + 1)
            decimal_point = len(amount_str) - decimals
            formatted = amount_str[:decimal_point] + "." + amount_str[decimal_point:]
            # Remove trailing zeros
            formatted = formatted.rstrip('0').rstrip('.')
            return formatted
        except Exception as e:
            logger.error(f"[WalletWatcher] Error formatting amount {amount} with decimals {decimals}: {e}", exc_info=True)
            return str(amount)

    def _process_token_transfer(self, log: Dict, wallet: str, chain: str) -> Optional[Dict]:
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
            
            # Get token metadata from correct chain
            w3 = Web3(Web3.HTTPProvider(self.config.get_rpc_url(chain)))
            token_metadata = self._get_token_metadata(w3, log['address'], chain)
            
            # Format amount with proper decimals
            formatted_amount = self._format_token_amount(value, token_metadata['decimals'])
            
            # Determine activity type based on wallet address
            activity_type = 'token_transfer_in' if to_address.lower() == wallet.lower() else 'token_transfer_out'
            
            return {
                'type': 'token_transfer',
                'activity_type': activity_type,
                'hash': log['transactionHash'],  # Already hex string
                'token': log['address'],
                'token_name': token_metadata['name'],
                'token_symbol': token_metadata['symbol'],
                'from': from_address,
                'to': to_address,
                'value': value,
                'formatted_amount': formatted_amount,
                'block_number': int(log['blockNumber'], 16),  # Convert hex to int
                'chain': chain,
                'wallet': wallet  # Add wallet address for matcher
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