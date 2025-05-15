import logging
from datetime import datetime
from typing import Dict, Any, List
from web3 import Web3
from eth_utils import to_checksum_address

from workers.market_monitor.services.wallet_tracker.base import Chain, ActivityType
from workers.market_monitor.utils.mongo import MongoJSONEncoder

logger = logging.getLogger(__name__)


class EVMWalletTracker:
    def __init__(self, chain: Chain, config: Any):
        self.chain = chain
        self.config = config
        self.w3 = chain.w3
        self.block_cache: Dict[str, int] = {}
        self.tx_cache: Dict[str, bool] = {}
        self.token_cache: Dict[str, Any] = {}
        self.balance_cache: Dict[str, float] = {}

        self.token_transfer_topic = (
            "0x" + Web3.keccak(text="Transfer(address,address,uint256)").hex()
        )
        self.erc1155_single_topic = (
            "0x"
            + Web3.keccak(
                text="TransferSingle(address,address,address,uint256,uint256)"
            ).hex()
        )
        self.erc1155_batch_topic = (
            "0x"
            + Web3.keccak(
                text="TransferBatch(address,address,address,uint256[],uint256[])"
            ).hex()
        )
        self.dex_routers = config.dex_routers
        self.erc20_abi = config.erc20_abi

    async def get_wallet_data(self, wallets: List[str]) -> Dict[str, Any]:
        logger.info(f"[EVMWalletTracker] Fetching {self.chain.value} data for wallets: {wallets}")
        if not self.w3.is_connected():
            logger.error(f"[EVMWalletTracker] Failed to connect to {self.chain.value} RPC")
            return {}

        result: Dict[str, Any] = {}
        current_block = self.w3.eth.block_number

        for wallet in wallets:
            try:
                addr = to_checksum_address(wallet)
                balance = self.w3.eth.get_balance(addr)
                cache_key = f"{self.chain.value}:{addr}"
                prev_balance = self.balance_cache.get(cache_key, self.w3.from_wei(balance, 'ether'))
                current_balance = self.w3.from_wei(balance, 'ether')
                self.balance_cache[cache_key] = current_balance
                balance_change = current_balance - prev_balance

                from_block = self.block_cache.get(cache_key, current_block - 100)
                logs: List[Any] = []

                def get_logs(filter_params):
                    try:
                        resp = self.w3.provider.make_request("eth_getLogs", [filter_params])
                        return resp.get("result", []) if isinstance(resp, dict) else []
                    except Exception as e:
                        logger.error(f"[EVMWalletTracker] RPC error: {e}", exc_info=True)
                        return []

                for topic in [self.token_transfer_topic, self.erc1155_single_topic, self.erc1155_batch_topic]:
                    logs.extend(
                        get_logs({
                            "fromBlock": hex(from_block),
                            "toBlock": hex(current_block),
                            "topics": [[topic]],
                            "address": None,
                        })
                    )

                filtered = []
                for log in logs:
                    try:
                        topics = log.get("topics", [])
                        if len(topics) >= 3:
                            frm = "0x" + topics[1][-40:]
                            to = "0x" + topics[2][-40:]
                            if addr.lower() in (frm.lower(), to.lower()):
                                filtered.append(log)
                    except Exception as e:
                        logger.warning(f"[EVMWalletTracker] Error filtering log: {e}", exc_info=True)

                transactions = self._process_wallet_logs(filtered, addr, balance_change)
                result[addr] = {
                    "chain": self.chain.value,
                    "balance": current_balance,
                    "transactions": transactions,
                    "last_updated": datetime.utcnow().isoformat(),
                }
                self.block_cache[cache_key] = current_block

            except Exception as e:
                logger.error(f"[EVMWalletTracker] Error processing {wallet}: {e}", exc_info=True)

        return result
    def _process_wallet_logs(self, logs: List[Any], wallet: str, balance_change: float) -> List[Any]:
        transactions = []
        tx_group: Dict[str, List[Any]] = {}

        for log in logs:
            txh = log.get("transactionHash")
            if not txh:
                continue
            tx_group.setdefault(txh, []).append(log)

        for txh, logs in tx_group.items():
            cache_key = f"{self.chain.value}:{txh}"
            if cache_key in self.tx_cache:
                continue
            self.tx_cache[cache_key] = True

            token_in = None
            token_out = None

            for log in logs:
                if log["topics"][0] == self.token_transfer_topic:
                    frm = "0x" + log["topics"][1][-40:]
                    to = "0x" + log["topics"][2][-40:]
                    data = log["data"] if log["data"].startswith("0x") else "0x" + log["data"]
                    val = int(data, 16)
                    meta = self._get_token_metadata(log["address"])
                    fmt = self._format_token_amount(val, meta["decimals"])
                    if frm.lower() == wallet.lower():
                        token_out = {
                            "address": log["address"],
                            "name": meta["name"],
                            "symbol": meta["symbol"],
                            "amount": val,
                            "formatted_amount": fmt
                        }
                    elif to.lower() == wallet.lower():
                        token_in = {
                            "address": log["address"],
                            "name": meta["name"],
                            "symbol": meta["symbol"],
                            "amount": val,
                            "formatted_amount": fmt
                        }

            if token_in and balance_change < 0:
                # Native sent, token received = Buy
                transactions.append({
                    "type": "token_trade",
                    "activity_type": "token_trade",
                    "hash": txh,
                    "wallet": wallet,
                    "wallet_name": wallet,
                    "chain": self.chain.value,
                    "token_in": "native",
                    "token_in_name": self.chain.value.upper(),
                    "token_in_symbol": self.config.get_native_symbol(self.chain.value),
                    "amount_in": int(abs(balance_change) * 10**18),
                    "formatted_amount_in": f"{abs(balance_change):.6f}",
                    "token_out": token_in["address"],
                    "token_out_name": token_in["name"],
                    "token_out_symbol": token_in["symbol"],
                    "amount_out": token_in["amount"],
                    "formatted_amount_out": token_in["formatted_amount"],
                    "block_number": int(logs[0]["blockNumber"], 16)
                })
            elif token_out and balance_change > 0:
                # Token sent, native received = Sell
                transactions.append({
                    "type": "token_trade",
                    "activity_type": "token_trade",
                    "hash": txh,
                    "wallet": wallet,
                    "wallet_name": wallet,
                    "chain": self.chain.value,
                    "token_in": token_out["address"],
                    "token_in_name": token_out["name"],
                    "token_in_symbol": token_out["symbol"],
                    "amount_in": token_out["amount"],
                    "formatted_amount_in": token_out["formatted_amount"],
                    "token_out": "native",
                    "token_out_name": self.chain.value.upper(),
                    "token_out_symbol": self.config.get_native_symbol(self.chain.value),
                    "amount_out": int(balance_change * 10**18),
                    "formatted_amount_out": f"{balance_change:.6f}",
                    "block_number": int(logs[0]["blockNumber"], 16)
                })
            else:
                # Not a trade, process as normal transfers
                for log in logs:
                    if log["topics"][0] == self.token_transfer_topic:
                        tx = self._process_token_transfer(log, wallet)
                        if tx:
                            transactions.append(tx)
                    elif log["topics"][0] in [self.erc1155_single_topic, self.erc1155_batch_topic]:
                        tx = self._process_erc1155_transfer(log, wallet)
                        if tx:
                            transactions.append(tx)

        return transactions

    def _process_token_transfer(self, log: Any, wallet: str) -> Any:
        try:
            frm = "0x" + log["topics"][1][-40:]
            to = "0x" + log["topics"][2][-40:]
            if wallet.lower() not in (frm.lower(), to.lower()):
                return None
            val = int(log["data"], 16)
            meta = self._get_token_metadata(log["address"])
            fmt = self._format_token_amount(val, meta["decimals"])
            activity = (
                "token_transfer_in"
                if to.lower() == wallet.lower()
                else "token_transfer_out"
            )
            return {
                "type": "token_transfer",
                "activity_type": activity,
                "hash": log["transactionHash"],
                "wallet": wallet,
                "wallet_name": wallet,
                "chain": self.chain.value,
                "from": frm,
                "to": to,
                "token": log["address"],
                "token_name": meta["name"],
                "token_symbol": meta["symbol"],
                "value": val,
                "formatted_amount": fmt,
                "block_number": int(log["blockNumber"], 16),
                "direction": "in" if to.lower() == wallet.lower() else "out",
                "is_self_transfer": frm.lower() == to.lower() == wallet.lower()
            }
        except Exception as e:
            logger.error(f"Error token transfer: {e}", exc_info=True)
            return None

    def _process_erc1155_transfer(self, log: Any, wallet: str) -> Any:
        try:
            tpcs = log["topics"]
            frm = "0x" + tpcs[2][-40:]
            to = "0x" + tpcs[3][-40:]
            if wallet.lower() not in (frm.lower(), to.lower()):
                return None
            data = log["data"][2:]
            if tpcs[0] == self.erc1155_single_topic:
                idv = int(data[:64], 16)
                val = int(data[64:], 16)
            else:
                snippet = data[64 * 2 :]
                idv = int(snippet[:64], 16)
                val = int(snippet[64:128], 16)
            activity = (
                ActivityType.NFT_TRANSFER_IN.value
                if to.lower() == wallet.lower()
                else ActivityType.NFT_TRANSFER_OUT.value
            )
            return {
                "type": "nft_transfer",
                "activity_type": activity,
                "hash": log["transactionHash"],
                "wallet": wallet,
                "wallet_name": wallet,
                "chain": self.chain.value,
                "collection": log["address"],
                "from": frm,
                "to": to,
                "token_id": idv,
                "amount": val,
                "block_number": int(log["blockNumber"], 16),
            }
        except Exception as e:
            logger.error(f"Error ERC1155: {e}", exc_info=True)
            return None

    def _get_token_metadata(self, addr: str) -> Dict[str, Any]:
        key = f"{self.chain.value}:{addr}"
        if key in self.token_cache:
            return self.token_cache[key]
        checksum = Web3.to_checksum_address(addr)
        contract = self.w3.eth.contract(address=checksum, abi=self.erc20_abi)
        try:
            name = contract.functions.name().call()
        except:
            name = f"Token-{checksum[:8]}"
        try:
            sym = contract.functions.symbol().call()
        except:
            sym = f"TKN-{checksum[:4]}"
        try:
            dec = contract.functions.decimals().call()
        except:
            dec = 18
        meta = {"name": name, "symbol": sym, "decimals": dec}
        self.token_cache[key] = meta
        return meta

    def _format_token_amount(self, amount: int, decimals: int) -> str:
        try:
            if decimals == 0:
                return str(amount)
            s = str(amount).zfill(decimals + 1)
            p = len(s) - decimals
            out = s[:p] + "." + s[p:]
            return out.rstrip("0").rstrip(".")
        except:
            return str(amount)
