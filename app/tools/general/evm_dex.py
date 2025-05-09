from web3 import Web3
from concurrent.futures import ThreadPoolExecutor, as_completed

class EvmDexClient:
    EVM_RPC = {
        "ethereum": "https://mainnet.infura.io/v3/979eaf5d833648778efe40f51fd44313",
        "base": "https://mainnet.base.org",
        "binance-smart-chain": "https://bsc-dataseed.binance.org/",
        "sonic": "https://rpc.soniclabs.com",
    }

    FACTORY_V2 = {
        "ethereum": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
        "base": "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6",
        "binance-smart-chain": "0xca143ce32fe78f1f7019d7d551a6402fc5350c73",
        "sonic": "0xEE4bC42157cf65291Ba2FE839AE127e3Cc76f741",
    }

    FACTORY_V3 = {
        "ethereum": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "base": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
        "binance-smart-chain": "0x1097053Fd2ea711dad45caCcc45EfF7548fCB362",
        "sonic": "0x3D91B700252e0E3eE7805d12e048a988Ab69C8ad",
    }

    QUOTER_ADDRESS = {
        "ethereum": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
        "base": "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",
        "binance-smart-chain": "0x78D78E420Da98ad378D7799bE8f4AF69033EB077",
        "sonic": "0x912060d9c7244A7601276c16CCb5be258F1335Df",
    }

    STABLES = {
        "ethereum": [
            "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        ],
        "binance-smart-chain": [
            "0x55d398326f99059fF775485246999027B3197955",
            "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
            "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        ],
        "base": [
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
        "0x4200000000000000000000000000000000000006",  # WETH
        ],
        "sonic": [
            "0x29219dd400f2Bf60E5a23d13Be72B486D4038894",  # USDC.e
            "0x039e2fB66102314Ce7b64Ce5Ce3E5183bc94aD38",  # S (native token)
        ],
    }

    FEE_TIERS = [100, 500, 2500, 10000]

    UNIV2_FACTORY_ABI = [{
        "constant": True,
        "inputs": [{"internalType": "address", "name": "tokenA", "type": "address"},
                   {"internalType": "address", "name": "tokenB", "type": "address"}],
        "name": "getPair",
        "outputs": [{"internalType": "address", "name": "pair", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }]

    UNIV3_FACTORY_ABI = [{
        "inputs": [{"internalType": "address", "name": "tokenA", "type": "address"},
                   {"internalType": "address", "name": "tokenB", "type": "address"},
                   {"internalType": "uint24", "name": "fee", "type": "uint24"}],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }]

    UNIV2_POOL_ABI = [
        {
            "constant": True,
            "inputs": [],
            "name": "getReserves",
            "outputs": [
                {"internalType": "uint112", "name": "_reserve0", "type": "uint112"},
                {"internalType": "uint112", "name": "_reserve1", "type": "uint112"},
                {"internalType": "uint32", "name": "_blockTimestampLast", "type": "uint32"},
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "token0",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "token1",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function",
        },
    ]

    QUOTER_ABI = [{
        "inputs": [
            {"internalType": "address", "name": "tokenIn", "type": "address"},
            {"internalType": "address", "name": "tokenOut", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
        ],
        "name": "quoteExactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }]

    ERC20_ABI = [
        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    ]

    def __init__(self, chain: str):
        self.chain = chain
        self.w3 = Web3(Web3.HTTPProvider(self.EVM_RPC[chain]))

    def _get_contract(self, address: str, abi: list):
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)

    def _get_token_metadata(self, token: str) -> dict:
        try:
            contract = self._get_contract(token, self.ERC20_ABI)
            return {
                "name": contract.functions.name().call(),
                "symbol": contract.functions.symbol().call(),
                "decimals": contract.functions.decimals().call(),
            }
        except Exception:
            return {"name": "", "symbol": "", "decimals": None}

    def get_v2_pair(self, tokenA: str, tokenB: str) -> str:
        factory_addr = self.FACTORY_V2.get(self.chain)
        if not factory_addr or int(factory_addr, 16) == 0:
            return ""
        factory = self._get_contract(factory_addr, self.UNIV2_FACTORY_ABI)
        pair = factory.functions.getPair(Web3.to_checksum_address(tokenA), Web3.to_checksum_address(tokenB)).call()
        return pair if int(pair, 16) != 0 else ""

    def get_v2_price(self, pool_address: str, token_in: str, token_out: str) -> dict:
        try:
            pool = self._get_contract(pool_address, self.UNIV2_POOL_ABI)
            reserves = pool.functions.getReserves().call()
            token0 = pool.functions.token0().call()
            token1 = pool.functions.token1().call()

            meta_in = self._get_token_metadata(token_in)
            meta_out = self._get_token_metadata(token_out)
            if meta_in["decimals"] is None or meta_out["decimals"] is None:
                return {"success": False, "error": "Cannot get decimals"}

            reserve_in = reserves[0] if Web3.to_checksum_address(token_in) == Web3.to_checksum_address(token0) else reserves[1]
            reserve_out = reserves[1] if reserve_in == reserves[0] else reserves[0]

            price = (reserve_out / (10 ** meta_out["decimals"])) / (reserve_in / (10 ** meta_in["decimals"]))

            return {
                "success": True,
                "price": price,
                "reserves": reserves,
                "token0": token0,
                "token1": token1,
                "decimals": {
                    "in": meta_in["decimals"],
                    "out": meta_out["decimals"],
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_v3_pool(self, tokenA: str, tokenB: str, fee: int) -> str:
        factory_addr = self.FACTORY_V3.get(self.chain)
        if not factory_addr or int(factory_addr, 16) == 0:
            return ""
        factory = self._get_contract(factory_addr, self.UNIV3_FACTORY_ABI)
        pool = factory.functions.getPool(Web3.to_checksum_address(tokenA), Web3.to_checksum_address(tokenB), fee).call()
        return pool if int(pool, 16) != 0 else ""

    def get_v3_price(self, token_in: str, token_out: str, fee: int, base_dec=18, quote_dec=6) -> dict:
        try:
            quoter_addr = self.QUOTER_ADDRESS.get(self.chain)
            if not quoter_addr or int(quoter_addr, 16) == 0:
                return {"success": False, "error": "Quoter not supported on this chain"}

            quoter = self._get_contract(quoter_addr, self.QUOTER_ABI)
            amount_in = 10 ** base_dec
            amount_out = quoter.functions.quoteExactInputSingle(
                Web3.to_checksum_address(token_in),
                Web3.to_checksum_address(token_out),
                fee,
                amount_in,
                0
            ).call()

            price = amount_out / (10 ** quote_dec)
            return {
                "success": True,
                "price": price,
                "amount_in": amount_in,
                "amount_out": amount_out,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_best_price_single_chain(self, token: str, base_dec=18, quote_dec=6) -> dict:
        stables = self.STABLES.get(self.chain, [])
        token_meta = self._get_token_metadata(token)
        if token_meta["decimals"] is None:
            return {"success": False, "error": "Không lấy được token metadata"}

        quote_meta_cache = {}

        def check_v2(stable):
            try:
                pair = self.get_v2_pair(token, stable)
                if pair:
                    result = self.get_v2_price(pair, token, stable)
                    if result["success"]:
                        quote_meta = quote_meta_cache.get(stable) or self._get_token_metadata(stable)
                        quote_meta_cache[stable] = quote_meta
                        return {
                            **result,
                            "price_in": f"1 {token_meta["symbol"]}",
                            "price_out": f"{result['price']} {quote_meta['symbol']}",
                            "pool": pair,
                            "chain": self.chain,
                            "type": "v2",
                            "address": token,
                            **token_meta,
                            "quote": stable,
                            **{"quote_" + k: v for k, v in quote_meta.items()},
                        }
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(check_v2, stable) for stable in stables]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    result["success"] = True
                    return result

        def check_v3(stable, fee):
            try:
                pool = self.get_v3_pool(token, stable, fee)
                if pool:
                    result = self.get_v3_price(token, stable, fee, base_dec, quote_dec)
                    if result["success"]:
                        quote_meta = quote_meta_cache.get(stable) or self._get_token_metadata(stable)
                        quote_meta_cache[stable] = quote_meta
                        return {
                            **result,
                            "price_in": f"1 {token_meta['symbol']}",
                            "price_out": f"{result['price']} {quote_meta['symbol']}",
                            "pool": pool,
                            "chain": self.chain,
                            "type": "v3",
                            "fee": fee,
                            "address": token,
                            **token_meta,
                            "quote": stable,
                            **{"quote_" + k: v for k, v in quote_meta.items()},
                        }
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(check_v3, stable, fee) for stable in stables for fee in self.FEE_TIERS]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    result["success"] = True
                    return result

        return {"success": False, "error": f"Không tìm thấy giá trên {self.chain}"}

    @classmethod
    def get_best_price(cls, token_address: str, base_dec=18, quote_dec=6) -> dict:
        results = []

        def fetch(chain):
            try:
                client = cls(chain)
                result = client.get_best_price_single_chain(token_address, base_dec, quote_dec)
                result["chain"] = chain
                return result
            except Exception as e:
                return {"success": False, "error": str(e), "chain": chain}

        with ThreadPoolExecutor(max_workers=min(8, len(cls.EVM_RPC))) as executor:
            futures = [executor.submit(fetch, chain) for chain in cls.EVM_RPC]
            for future in as_completed(futures):
                result = future.result()
                if result.get("success"):
                    return result
                results.append(result)

        return {"success": False, "error": "Không tìm thấy giá trên bất kỳ chain nào.", "details": results}