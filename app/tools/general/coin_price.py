import requests
import re
from app.tools.general.evm_dex import EvmDexClient
from app.configs import app_configs
from app.utils.call_api import call_api

def is_evm_address(addr: str) -> bool:
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", addr))

def is_solana_address(addr: str) -> bool:
    return bool(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", addr))

def get_solana_price_via_jupiter(token_address: str, amount: int = 10**6) -> dict:
    try:
        url = (
            f"https://quote-api.jup.ag/v6/quote"
            f"?inputMint={token_address}"
            f"&outputMint=EPjFWdd5AufqSSqeM2qA9G4Kfuz5F8bG6hK23zyB6h7E"
            f"&amount={amount}"
        )
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                return {"success": True, "data": data["data"][0], "source": "jupiter"}
            return {"success": False, "error": "Không có quote từ Jupiter."}
        return {"success": False, "error": f"Jupiter API lỗi ({resp.status_code})"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_token_price(asset: str, amount: int = 10**6) -> dict:
    coingecko_url = app_configs.API_CONF["coingecko"]["url"]
    coingecko_api_key = app_configs.API_CONF["coingecko"]["api_key"]
    headers = {"x-cg-demo-api-key": coingecko_api_key}

    # EVM address
    if is_evm_address(asset):
        for chain in ["ethereum", "base", "binance-smart-chain", "sonic"]:
            url = f"/coins/{chain}/contract/{asset}"
            resp = await call_api(coingecko_url + url, method="GET", headers=headers)
            if resp["success"]:
                resp["source"] = f"coingecko:{chain}"
                return resp
            else:
                print(f"[WARN] CoinGecko ({chain}) không trả về giá: {resp.get('error')}")

        for chain in ["ethereum", "base", "binance-smart-chain", "sonic"]:
            try:
                client = EvmDexClient(chain)
                price_result = client.get_best_price(asset)
                if price_result["success"]:
                    price_result["source"] = f"dex:{chain}"
                    return price_result
            except Exception as e:
                print(f"[ERROR] Lỗi khi gọi DEX client {chain}: {e}")
        return {"success": False, "error": "Không tìm thấy giá trên CoinGecko hoặc DEX cho địa chỉ EVM này."}

    # Solana address
    elif is_solana_address(asset):
        url = f"/coins/solana/contract/{asset}"
        resp = await call_api(coingecko_url + url, method="GET", headers=headers)
        if resp["success"]:
            resp["source"] = "coingecko:solana"
            return resp
        else:
            print(f"[WARN] CoinGecko Solana không có giá: {resp.get('error')}")

        jup_result = get_solana_price_via_jupiter(asset, amount)
        if jup_result["success"]:
            return jup_result
        return {"success": False, "error": "Không tìm thấy giá trên CoinGecko hoặc Jupiter cho địa chỉ Solana này."}

    # Symbol or name
    else:
        search_url = f"/search?query={asset}"
        resp = await call_api(coingecko_url + search_url, method="GET", headers=headers)
        if resp["success"]:
            results = resp["data"].get("coins", [])
            if results:
                coin_id = results[0]["id"]
                detail_url = (
                    f"/coins/{coin_id}"
                    f"?localization=false&tickers=false&community_data=false"
                    f"&developer_data=false&sparkline=false"
                )
                detail_resp = await call_api(coingecko_url + detail_url, method="GET", headers=headers)
                if detail_resp["success"]:
                    detail_resp["source"] = f"coingecko:id:{coin_id}"
                    return detail_resp
                else:
                    return {"success": False, "error": "Không lấy được chi tiết CoinGecko."}
            return {"success": False, "error": "Không tìm thấy token theo tên/symbol."}
        return {"success": False, "error": "Lỗi khi gọi API search CoinGecko."}
