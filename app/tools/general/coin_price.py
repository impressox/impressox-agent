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
                ohlc_1d_resp = await call_api(f"{coingecko_url}/coins/{coin_id}/ohlc?vs_currency=usd&days=1", method="GET", headers=headers)
                ohlc_7d_resp = await call_api(f"{coingecko_url}/coins/{coin_id}/ohlc?vs_currency=usd&days=7", method="GET", headers=headers)

                if detail_resp["success"] and ohlc_1d_resp["success"] and ohlc_7d_resp["success"]:
                    data = detail_resp["data"]
                    ohlc_1d = ohlc_1d_resp["data"]
                    ohlc_7d = ohlc_7d_resp["data"]

                    analysis_results = {
                        "30m": {
                            "ohlc_data": ohlc_1d[-2:],  # chỉ trả về 2 nến cuối
                            "analysis": analyze_breakout_and_volatility(ohlc_1d[-4:], 1)
                        },
                        "1h": {
                            "ohlc_data": group_ohlc(ohlc_1d, group_size=2)[-2:],
                            "analysis": analyze_breakout_and_volatility(group_ohlc(ohlc_1d, 2), 2)
                        },
                        "4h": {
                            "ohlc_data": group_ohlc(ohlc_7d, group_size=8)[-2:],
                            "analysis": analyze_breakout_and_volatility(group_ohlc(ohlc_7d, 8), 8)
                        }
                    }

                    simplified_data = {
                        "id": data.get("id"),
                        "symbol": data.get("symbol"),
                        "name": data.get("name"),
                        "description": data.get("description", {}).get("en"),
                        "homepage": data.get("links", {}).get("homepage", [None])[0],
                        "twitter": data.get("links", {}).get("twitter_screen_name"),
                        "reddit": data.get("links", {}).get("subreddit_url"),
                        "github": data.get("links", {}).get("repos_url", {}).get("github"),
                        "image": data.get("image", {}).get("large"),
                        "genesis_date": data.get("genesis_date"),
                        "categories": data.get("categories"),
                        "market_cap_rank": data.get("market_cap_rank"),
                        "watchlist_portfolio_users": data.get("watchlist_portfolio_users"),
                        "hashing_algorithm": data.get("hashing_algorithm"),
                        "block_time_in_minutes": data.get("block_time_in_minutes"),
                        "roi": data.get("market_data", {}).get("roi"),
                        "sentiment": {
                            "up": data.get("sentiment_votes_up_percentage"),
                            "down": data.get("sentiment_votes_down_percentage")
                        },
                        "public_notice": data.get("public_notice"),
                        "detail_platforms": data.get("detail_platforms"),
                        "market_data": {
                            "current_price_usd": data.get("market_data", {}).get("current_price", {}).get("usd"),
                            "market_cap_usd": data.get("market_data", {}).get("market_cap", {}).get("usd"),
                            "total_volume_usd": data.get("market_data", {}).get("total_volume", {}).get("usd"),
                            "fully_diluted_valuation_usd": data.get("market_data", {}).get("fully_diluted_valuation", {}).get("usd"),
                            "ath_usd": data.get("market_data", {}).get("ath", {}).get("usd"),
                            "ath_date_usd": data.get("market_data", {}).get("ath_date", {}).get("usd"),
                            "ath_change_percentage_usd": data.get("market_data", {}).get("ath_change_percentage", {}).get("usd"),
                            "atl_usd": data.get("market_data", {}).get("atl", {}).get("usd"),
                            "atl_date_usd": data.get("market_data", {}).get("atl_date", {}).get("usd"),
                            "atl_change_percentage_usd": data.get("market_data", {}).get("atl_change_percentage", {}).get("usd"),
                            "price_change_percentage_1h": data.get("market_data", {}).get("price_change_percentage_1h_in_currency", {}).get("usd"),
                            "price_change_percentage_24h": data.get("market_data", {}).get("price_change_percentage_24h_in_currency", {}).get("usd"),
                            "price_change_percentage_7d": data.get("market_data", {}).get("price_change_percentage_7d_in_currency", {}).get("usd"),
                            "price_change_percentage_14d": data.get("market_data", {}).get("price_change_percentage_14d_in_currency", {}).get("usd"),
                            "price_change_percentage_30d": data.get("market_data", {}).get("price_change_percentage_30d_in_currency", {}).get("usd"),
                            "price_change_percentage_60d": data.get("market_data", {}).get("price_change_percentage_60d_in_currency", {}).get("usd"),
                            "price_change_percentage_1y": data.get("market_data", {}).get("price_change_percentage_1y"),
                            "high_24h": data.get("market_data", {}).get("high_24h", {}).get("usd"),
                            "low_24h": data.get("market_data", {}).get("low_24h", {}).get("usd"),
                            "price_change_24h": data.get("market_data", {}).get("price_change_24h")
                        },
                        "ohlc_analysis": analysis_results,
                        "source": f"coingecko:id:{coin_id}", 
                    }
                    simplified_data["summary"] = generate_summary(simplified_data)
                    return {"success": True, "data": clean_data(simplified_data)}

                return {"success": False, "error": "Không lấy được chi tiết hoặc dữ liệu OHLC CoinGecko."}
            return {"success": False, "error": "Không tìm thấy token theo tên/symbol."}
        return {"success": False, "error": "Lỗi khi gọi API search CoinGecko."}
    
def generate_summary(data: dict) -> str:
    name = data.get("name", "Unknown")
    symbol = data.get("symbol", "").upper()
    price = data.get("market_data", {}).get("current_price_usd", 0)
    market_cap = data.get("market_data", {}).get("market_cap_usd", 0)
    ath = data.get("market_data", {}).get("ath_usd", 0)
    ath_change = data.get("market_data", {}).get("ath_change_percentage_usd", 0)
    change_24h = data.get("market_data", {}).get("price_change_percentage_24h", 0)
    sentiment_up = data.get("sentiment", {}).get("up", 0)
    sentiment_down = data.get("sentiment", {}).get("down", 0)

    breakout_30m = data.get("ohlc_analysis", {}).get("30m", {}).get("analysis", {}).get("breakout_signal", "Unknown")
    breakout_1h = data.get("ohlc_analysis", {}).get("1h", {}).get("analysis", {}).get("breakout_signal", "Unknown")
    breakout_4h = data.get("ohlc_analysis", {}).get("4h", {}).get("analysis", {}).get("breakout_signal", "Unknown")

    lines = [
        f"*{name} ({symbol})*\n",
        f"*Price*: `${price:,.2f}` USD",
        f"*24h Change*: `{change_24h:+.2f}%`",
        f"*Market Cap*: `${market_cap / 1e9:.2f}B`",
        f"*ATH*: `${ath:,.2f}` ({abs(ath_change):.0f}% {'below' if ath_change < 0 else 'above'})",
        f"*Sentiment*: `{sentiment_up:.0f}%` 👍 / `{sentiment_down:.0f}%` 👎",
        "",
        f"*Breakout Signals*:",
        f"- 30m: `{breakout_30m}`",
        f"- 1h: `{breakout_1h}`",
        f"- 4h: `{breakout_4h}`"
    ]

    # Optional advice
    if breakout_1h == "Breakout tăng" and sentiment_up > 70:
        lines.append("\n🚀 *Bullish signal detected* – strong positive sentiment. Worth monitoring.")
    elif breakout_1h == "Breakout giảm" and change_24h < -3:
        lines.append("\n⚠️ *Bearish momentum* in 1h timeframe. Consider risk management.")

    return "\n".join(lines)


def clean_data(data):
    """Đệ quy lọc bỏ các trường có giá trị None, rỗng chuỗi hoặc mảng"""
    if isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items() if v not in (None, "", [], {})}
    elif isinstance(data, list):
        return [clean_data(item) for item in data if item not in (None, "", [], {})]
    else:
        return data

def group_ohlc(data, group_size):
    grouped = []
    for i in range(0, len(data), group_size):
        chunk = data[i:i+group_size]
        if len(chunk) < group_size:
            continue
        timestamp = chunk[0][0]
        open_price = chunk[0][1]
        high_price = max(c[2] for c in chunk)
        low_price = min(c[3] for c in chunk)
        close_price = chunk[-1][4]
        grouped.append([timestamp, open_price, high_price, low_price, close_price])
    return grouped

def analyze_breakout_and_volatility(ohlc_grouped, group_size):
    if len(ohlc_grouped) < 2:
        return {}

    latest = ohlc_grouped[-1]
    previous = ohlc_grouped[-2]

    if latest[4] > previous[2]:
        signal = "Bullish breakout"
    elif latest[4] < previous[3]:
        signal = "Bearish breakout"
    else:
        signal = "No breakout"


    avg_range = sum([row[2] - row[3] for row in ohlc_grouped]) / len(ohlc_grouped)

    return {
        "breakout_signal": signal,
        "latest_close": latest[4],
        "previous_high": previous[2],
        "previous_low": previous[3],
        "avg_price_range": round(avg_range, 4),
        "timeframe_minutes": group_size * 30
    }