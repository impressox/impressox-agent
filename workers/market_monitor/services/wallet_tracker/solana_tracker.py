import logging
import json
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List
from solders.pubkey import Pubkey
from solders.rpc.responses import GetTransactionResp
import base64
import re

from .base import Chain

logger = logging.getLogger(__name__)
JUPITER_TOKENLIST_URL = "https://token.jup.ag/all"
CACHE_FILE = "monitor_cache/jupiter_tokenlist_cache.json"
CACHE_DURATION = timedelta(days=1)
SOLANA_DEX_PROGRAMS = {
    # Jupiter Aggregator
    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB": "Jupiter",

    # Raydium
    "4ckmDgGz5U5vPffH2E7JhTg2tZTQTKCq9p6k8R6KjELp": "Raydium AMM",
    "RVKd61ztZW9C8hwrqzABffp5cqpHkK3eKsiV4Twc8KJ": "Raydium CLMM",
    "EhhTK6JMQNYL1L2Acxg6aR1RniybuUoPMAXwrZb2oJvR": "Raydium V2",
    "C6Prr26v8Cfsb6gTVA5rjtwTj5wumU2XXdUB3vu3kz4E": "Raydium Staking",
    # Raydium OpenBook Market
    "EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o": "Raydium Market",

    # Orca
    "82yxjeMs5N6V4o4J5E2JY2vHX15wGZ8iYv2iA6cUj9tF": "Orca AMM",
    "nEXsVmkWRzGrg9tZxTZtmjUL1mT5jg3ZCDtZ8KQX5oM": "Orca Whirlpools",
    "DmcX3X2d6HTkTc9QpTnXVyVoFXzopnyvFWJnvkfT8qTQ": "Orca CLMM",

    # Phoenix (Orderbook DEX)
    "PHoenixR2YwdR9JbDZrjcfHcxy3hrMRYyM5ZbS6tG9dw": "Phoenix",

    # Lifinity
    "C6Prr26v8Cfsb6gTVA5rjtwTj5wumU2XXdUB3vu3kz4E": "Lifinity",

    # Meteora
    "8U9bKXggg2VWv48eEbSSt3PvxK2tq7qfK7tSiJ97ViwA": "Meteora",

    # OpenBook (Serum successor)
    "9xQeWvG816bUx9EPY2Xy9xSvyX5Avjxi5GkT9YGyjGkR": "OpenBook/Serum",

    # Cyclos (CLMM)
    "CYCLoL4CqaNoJw8uQpS8TFxyqwjqAhWXgpS4GGweVLj9": "Cyclos",

    # Step Finance
    "SwaPpKchHy4ayV8hDKj6J7KHjiJ9v79QxA4pCz7B9pNX": "Step Finance",

    # Saber (stablecoin swap)
    "SaberESwo3Y1wXrP7tyuaMZqPEzA4usXTVEtuUbtLq5": "Saber",

    # GooseFX
    "GooSfx6A3C7wCk37FvJZC2wvZTjUjhyNzt7nF3yEPuZg": "GooseFX",

    # Symmetry
    "SYMMETRYp7kM7nbd1p5K4c2We5oabgPkEuhRYT14VhGe": "Symmetry",

    # Cropper
    "CrpErQZbCxEyidb5c5n9NEJHprkD9bKDF7Rb2vYvP8Q": "Cropper",

    # Lifinity V2
    "LiFhnrswYbFf9NSNcpgNEEzzV8DaFAL6kYXu7URXBLf": "Lifinity V2",

    # Aldrin
    "ALdrinmxVkqV2w1TLWGrRFSTKJLHsbE1v1tRSBvaD2wE": "Aldrin",

    # Penguin
    "PENGUINss5kM65gCnGBeEXcHid6iSv6QHZWb2Y6MT1Q": "Penguin",
    
    # Mango Markets (V3)
    "mangoJpV4nF5js7W9KCh3NT7xhMpwXgRax4kgJz57w": "Mango Markets",

    # Drift Protocol
    "DRiFTQK6ZQukapCyDCf7UZz4j9FF3YY6stjMQuwM6v2": "Drift",
    
    # Invariant
    "inv1qQAc9H3vXTivDK4iYAzYeH9FCDxwnZgy73PJZCs": "Invariant",

    # Balansol
    "BaLaNsoLFzM5Atc2vhyraAfCyX5tqCVDfF49mMycX5i": "Balansol",
}

def load_jupiter_tokenlist():
    # Kiểm tra file cache tồn tại và chưa hết hạn
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        cache_time = datetime.fromisoformat(cache.get("_cache_time"))
        if datetime.utcnow() - cache_time < CACHE_DURATION:
            return cache["tokens"]
    # Nếu hết hạn hoặc chưa có, fetch mới
    response = requests.get(JUPITER_TOKENLIST_URL)
    if response.status_code == 200:
        token_list = response.json()
        cache = {
            "_cache_time": datetime.utcnow().isoformat(),
            "tokens": token_list
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        return token_list
    else:
        raise Exception(f"Failed to fetch Jupiter tokenlist: {response.status_code}")

def build_token_dict(token_list):
    return {token['address']: token for token in token_list}

def get_dex_name(logs, account_keys):
    # Ưu tiên đọc log nếu có tên cụ thể
    for log in logs:
        log_lower = log.lower()
        if "jupiter" in log_lower:
            return "Jupiter"
        if "orca" in log_lower:
            return "Orca"
        if "raydium" in log_lower:
            return "Raydium"
        if "serum" in log_lower:
            return "Serum"
        if "MeteoraDlmm" in log:
            return "MeteoraDlmm"
        if "Program log: SwapEvent" in log:
            match = re.search(r"dex:\s*([A-Za-z0-9_]+)", log)
            if match:
                return match.group(1)
    # Không có tên trong log, tra account_keys
    for key in account_keys:
        key_str = str(key)
        if key_str in SOLANA_DEX_PROGRAMS:
            return SOLANA_DEX_PROGRAMS[key_str]
    return "Unknown"

class SolanaWalletTracker:
    def __init__(self):
        self.chain = Chain.SOLANA
        self.token_cache = {}
        self.block_cache = {}
        self.tx_cache = {}
        self.jupiter_tokens = build_token_dict(load_jupiter_tokenlist())

    async def _get_token_metadata(self, mint: str) -> dict:
        if mint in self.token_cache and all(k in self.token_cache[mint] for k in ("name", "symbol", "decimals")):
            return self.token_cache[mint]

        if mint == "native":
            return {"name": "Solana", "symbol": "SOL", "decimals": 9}

        # 1. Tra Jupiter tokenlist cache
        if mint in self.jupiter_tokens:
            token = self.jupiter_tokens[mint]
            result = {
                "name": token.get("name", "Unknown Token"),
                "symbol": token.get("symbol", "Unknown"),
                "decimals": token.get("decimals", 0)
            }
            self.token_cache[mint] = result
            return result

        result = {"name": "Unknown Token", "symbol": "Unknown", "decimals": 0}
        client = self.chain.solana_client

        # 2. Fallback: Onchain mint (decimals)
        try:
            mint_pubkey = Pubkey.from_string(mint)
            mint_info = await client.get_account_info(mint_pubkey)
            if mint_info and mint_info.value and mint_info.value.data:
                mint_data = base64.b64decode(mint_info.value.data[0])
                if len(mint_data) >= 45:
                    result["decimals"] = mint_data[44]
        except Exception as e:
            logger.warning(f"Error fetching decimals from mint {mint}: {e}")

        # 3. Fallback: Metaplex metadata (name, symbol)
        try:
            metadata_program_id = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
            seeds = [b"metadata", bytes(metadata_program_id), bytes(mint_pubkey)]
            metadata_address, _ = Pubkey.find_program_address(seeds, metadata_program_id)
            meta_info = await client.get_account_info(metadata_address)
            if meta_info and meta_info.value and meta_info.value.data:
                meta_data = base64.b64decode(meta_info.value.data[0])
                if len(meta_data) > 45:
                    name = meta_data[4:36].decode("utf-8").rstrip("\x00")
                    symbol = meta_data[36:45].decode("utf-8").rstrip("\x00")
                    result["name"] = name if name else "Unknown Token"
                    result["symbol"] = symbol if symbol else "Unknown"
        except Exception as e:
            logger.warning(f"Error fetching metadata for {mint}: {e}")

        self.token_cache[mint] = result
        return result

    def _format_token_amount(self, amount: int, decimals: int) -> str:
        try:
            if decimals == 0:
                return str(amount)
            amount_str = str(amount).zfill(decimals + 1)
            decimal_point = len(amount_str) - decimals
            formatted = amount_str[:decimal_point] + "." + amount_str[decimal_point:]
            return formatted.rstrip('0').rstrip('.')
        except Exception as e:
            logger.error(f"[WalletWatcher] Error formatting amount: {e}")
            return str(amount)

    def _parse_solana_swap(self, tx_data: GetTransactionResp, wallet: str) -> dict:
        try:
            meta = tx_data.value.transaction.meta
            logs = meta.log_messages or []
            pre_token_balances = meta.pre_token_balances or []
            post_token_balances = meta.post_token_balances or []
            pre_balances = meta.pre_balances or []
            post_balances = meta.post_balances or []
            fee = meta.fee or 0

            swap_result = {
                "status": "failed",
                "dex": None,
                "from_token": None,
                "to_token": None,
                "fee": fee / 1e9,
            }

            token_deltas = {}
            wallet_token_accounts = set()
            for balance in pre_token_balances + post_token_balances:
                if str(balance.owner) == wallet:
                    wallet_token_accounts.add(str(balance.mint))

            for mint in wallet_token_accounts:
                pre_amount = 0
                post_amount = 0
                decimals = 9
                for balance in pre_token_balances:
                    if str(balance.mint) == mint and str(balance.owner) == wallet:
                        pre_amount += int(balance.ui_token_amount.amount)
                        decimals = balance.ui_token_amount.decimals
                for balance in post_token_balances:
                    if str(balance.mint) == mint and str(balance.owner) == wallet:
                        post_amount += int(balance.ui_token_amount.amount)
                        decimals = balance.ui_token_amount.decimals
                delta = post_amount - pre_amount
                if delta != 0:
                    token_deltas[mint] = {
                        "mint": mint,
                        "symbol": mint[:4].upper(),
                        "amount": abs(delta) / (10 ** decimals),
                        "decimals": decimals,
                        "delta": delta
                    }

            wallet_index = None
            for i, _ in enumerate(pre_balances):
                wallet_index = i
                break

            if wallet_index is not None and wallet_index < len(pre_balances) and wallet_index < len(post_balances):
                sol_change = post_balances[wallet_index] - pre_balances[wallet_index] + fee
                if sol_change != 0:
                    token_deltas["native"] = {
                        "mint": "native",
                        "symbol": "SOL",
                        "amount": abs(sol_change) / 1e9,
                        "decimals": 9,
                        "delta": sol_change
                    }

            from_token = next((v for v in token_deltas.values() if v["delta"] < 0), None)
            to_token = next((v for v in token_deltas.values() if v["delta"] > 0), None)

            if from_token:
                swap_result["from_token"] = from_token
            if to_token:
                swap_result["to_token"] = to_token

            if from_token and to_token and meta.err is None:
                swap_result["status"] = "success"
            
            account_keys = self._extract_account_keys(tx_data)
            swap_result["dex"] = get_dex_name(logs, account_keys)

            return swap_result
        except Exception as e:
            logger.error(f"[WalletWatcher] Error in _parse_solana_swap: {e}")
            return {"status": "error", "message": str(e)}

    async def get_wallet_data(self, wallets: List[str]) -> Dict:
        result = {}
        client = self.chain.solana_client

        latest_slot_resp = await client.get_slot(commitment="finalized")
        if not latest_slot_resp or not latest_slot_resp.value:
            return {}
        latest_slot = latest_slot_resp.value

        for wallet in wallets:
            try:
                pubkey = Pubkey.from_string(wallet)
                balance_resp = await client.get_balance(pubkey, commitment="finalized")
                if balance_resp is None:
                    continue
                sol_balance = balance_resp.value / 1e9
                cache_key = f"{self.chain.value}:{wallet}"
                last_slot = self.block_cache.get(cache_key)

                signatures_resp = await client.get_signatures_for_address(pubkey, limit=20, commitment="finalized")
                if not signatures_resp or not signatures_resp.value:
                    continue

                signatures = signatures_resp.value
                transactions = []
                highest_slot = last_slot if last_slot else 0

                for sig_info in signatures:
                    try:
                        tx_hash = str(sig_info.signature)
                        if tx_hash in self.tx_cache:
                            continue
                        if sig_info.slot > highest_slot:
                            highest_slot = sig_info.slot
                        if latest_slot - sig_info.slot > 1000:
                            continue

                        tx_data = await client.get_transaction(
                            sig_info.signature,
                            max_supported_transaction_version=0,
                            commitment="finalized",
                            encoding="jsonParsed"
                        )
                        if not tx_data or not tx_data.value:
                            continue

                        meta = tx_data.value.transaction.meta
                        logs = meta.log_messages or []

                        # Token trade (swap)  
                        swap_info = self._parse_solana_swap(tx_data, wallet)
                        if swap_info['status'] == 'success' and swap_info.get('from_token') and swap_info.get('to_token'):
                            from_token = swap_info['from_token']
                            to_token = swap_info['to_token']
                            token_in_mint = from_token['mint']
                            token_in_decimals = from_token['decimals']
                            token_out_mint = to_token['mint']
                            token_out_decimals = to_token['decimals']
                            token_in_meta = await self._get_token_metadata(token_in_mint)
                            token_out_meta = await self._get_token_metadata(token_out_mint)
                            # Lấy symbol và name đúng async
                            token_in_symbol = token_in_meta['symbol']
                            token_in_name = token_in_meta['name']
                            token_out_symbol = token_out_meta['symbol']
                            token_out_name = token_out_meta['name']

                            token_in_amount_raw = int(from_token['amount'] * (10 ** token_in_decimals))
                            token_out_amount_raw = int(to_token['amount'] * (10 ** token_out_decimals))
                            formatted_amount_in = self._format_token_amount(token_in_amount_raw, token_in_decimals)
                            formatted_amount_out = self._format_token_amount(token_out_amount_raw, token_out_decimals)

                            side = 'buy' if token_in_mint == 'native' else ('sell' if token_out_mint == 'native' else 'unknown')

                            transactions.append({
                                'type': 'token_trade',
                                'activity_type': 'token_trade',
                                'hash': tx_hash,
                                'wallet': wallet,
                                'wallet_name': wallet,
                                'side': side,
                                'token_in': token_in_mint,
                                'token_in_name': token_in_name,
                                'token_in_symbol': token_in_symbol,
                                'token_in_amount': token_in_amount_raw,
                                'formatted_amount_in': formatted_amount_in,
                                'token_in_decimals': token_in_decimals,
                                'token_out': token_out_mint,
                                'token_out_name': token_out_name,
                                'token_out_symbol': token_out_symbol,
                                'token_out_amount': token_out_amount_raw,
                                'formatted_amount_out': formatted_amount_out,
                                'token_out_decimals': token_out_decimals,
                                'block_number': tx_data.value.slot,
                                'dex_name': swap_info.get('dex'),
                                'timestamp': datetime.fromtimestamp(tx_data.value.block_time).isoformat() if tx_data.value.block_time else None,
                                'fee': swap_info.get('fee', 0)
                            })
                            self.tx_cache[tx_hash] = True
                            continue

                        # NFT transfer detection
                        for balance in meta.post_token_balances or []:
                            # Xác định đây là NFT (decimals==0, amount==1)
                            if balance.ui_token_amount.decimals == 0 and int(balance.ui_token_amount.amount) == 1:
                                mint = str(balance.mint)
                                direction = 'in' if str(balance.owner) == wallet else 'out'
                                mint_meta = await self._get_token_metadata(mint)
                                nft_symbol = mint_meta['symbol']
                                nft_name = mint_meta['name']
                                transactions.append({
                                    'activity_type': f'nft_transfer_{direction}',
                                    'type': 'nft_transfer',
                                    'hash': tx_hash,
                                    'wallet': wallet,
                                    'wallet_name': wallet,
                                    'mint': mint,
                                    'nft_symbol': nft_symbol,
                                    'nft_name': nft_name,
                                    'native_symbol': 'SOL',
                                    'amount': 1,
                                    'block_number': tx_data.value.slot,
                                    'timestamp': datetime.fromtimestamp(tx_data.value.block_time).isoformat() if tx_data.value.block_time else None,
                                    'fee': meta.fee / 1e9 if meta.fee else 0
                                })

                        # NFT trade (marketplace)
                        if any("Instruction: Sell" in msg or "Instruction: Buy" in msg for msg in logs):
                            account_keys = self._extract_account_keys(tx_data)
                            pre_balances = meta.pre_balances or []
                            post_balances = meta.post_balances or []
                            sol_paid = None
                            counterparty = None
                            direction = None

                            if wallet in account_keys:
                                idx = account_keys.index(wallet)
                                if idx < len(pre_balances) and idx < len(post_balances):
                                    sol_delta = post_balances[idx] - pre_balances[idx] + (meta.fee or 0)
                                    if sol_delta < -0.000001:
                                        sol_paid = abs(sol_delta)
                                        direction = 'buy'
                                        # Counterparty là ví nhận NFT, bạn có thể extract từ log hoặc balance change
                                        # Nếu có trường owner cũ, bạn lấy từ pre/post token_balances, ví dụ:
                                        for balance in meta.pre_token_balances or []:
                                            if int(balance.ui_token_amount.amount) == 1 and str(balance.owner) != wallet:
                                                counterparty = str(balance.owner)
                                                break
                                    elif sol_delta > 0.000001:
                                        sol_paid = abs(sol_delta)
                                        direction = 'sell'
                                        for balance in meta.post_token_balances or []:
                                            if int(balance.ui_token_amount.amount) == 1 and str(balance.owner) != wallet:
                                                counterparty = str(balance.owner)
                                                break

                            # Lấy NFT mint (collection) từ balance changes
                            nft_mint = None
                            for balance in meta.post_token_balances or []:
                                if int(balance.ui_token_amount.amount) == 1 and str(balance.owner) == wallet:
                                    nft_mint = str(balance.mint)
                                    break

                            transactions.append({
                                'type': 'nft_trade',
                                'activity_type': 'nft_trade',
                                'hash': tx_hash,
                                'wallet': wallet,
                                'wallet_name': wallet,
                                'chain': 'solana',
                                'collection': nft_mint,
                                'token_id': nft_mint,  # Solana không có token_id, có thể để chính là mint
                                'amount': 1,
                                'direction': direction or 'trade',
                                'counterparty': counterparty,
                                'price_token': "So11111111111111111111111111111111111111112",  # native SOL
                                'price_token_symbol': 'SOL',
                                'price_token_amount': sol_paid or 0,
                                'formatted_price': f"{(sol_paid or 0) / 1e9:.4f}",
                                'block_number': tx_data.value.slot,
                                'timestamp': datetime.fromtimestamp(tx_data.value.block_time).isoformat() if tx_data.value.block_time else None,
                                'fee': meta.fee / 1e9 if meta.fee else 0,
                            })

                        # Native SOL transfer detection - xác định real amount
                        account_keys = self._extract_account_keys(tx_data)
                        pre_balances = meta.pre_balances or []
                        post_balances = meta.post_balances or []

                        if wallet in account_keys:
                            idx = account_keys.index(wallet)
                            if idx < len(pre_balances) and idx < len(post_balances):
                                sol_delta = post_balances[idx] - pre_balances[idx] + (meta.fee or 0)
                                # Chỉ log nếu khác biệt lớn hơn 0.000001 SOL (đề phòng lỗi làm tròn)
                                if abs(sol_delta) > 0.000001:
                                    direction = 'in' if sol_delta > 0 else 'out'
                                    transactions.append({
                                        'activity_type': f'native_transfer_{direction}',
                                        'type': 'native_transfer',
                                        'hash': tx_hash,
                                        'wallet': wallet,
                                        'wallet_name': wallet,
                                        'native_symbol': 'SOL',
                                        'amount': abs(sol_delta) / 1e9,
                                        'block_number': tx_data.value.slot,
                                        'timestamp': datetime.fromtimestamp(tx_data.value.block_time).isoformat() if tx_data.value.block_time else None,
                                        'fee': meta.fee / 1e9 if meta.fee else 0
                                    })

                        self.tx_cache[tx_hash] = True

                    except Exception as e:
                        logger.error(f"[WalletWatcher] Error processing tx {tx_hash}: {e}")

                if highest_slot > 0:
                    self.block_cache[cache_key] = highest_slot

                result[wallet] = {
                    'chain': 'solana',
                    'balance': sol_balance,
                    'transactions': transactions,
                    'last_updated': datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"[WalletWatcher] Error processing wallet {wallet}: {e}")

        return result
    
    def _extract_account_keys(self, tx_data):
        txn = tx_data.value.transaction
        # Nếu là object (solders)
        if hasattr(txn, "message"):
            return [str(k) for k in txn.message.account_keys]
        if hasattr(txn, "transaction") and hasattr(txn.transaction, "message"):
            return [str(k) for k in txn.transaction.message.account_keys]
        # Nếu là dict (jsonParsed)
        if isinstance(txn, dict):
            msg = txn.get("message", {})
            return [k for k in msg.get("accountKeys", [])]
        return []
