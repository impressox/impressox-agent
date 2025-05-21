import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
import aiohttp
from src.errors import BinanceAPIError, ConnectionError, ServiceError
from src.types import (
    MarketInfo, 
    MarketInfoData, 
    Trade, 
    MarketPair,
    AlphaAnalysis,
    AlphaInsight
)

logger = logging.getLogger(__name__)

class BinanceService:
    """Service for interacting with Binance API"""
    
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Add API key if available
        if api_key := os.getenv("BINANCE_API_KEY"):
            self.headers["X-MBX-APIKEY"] = api_key

    async def _get(self, endpoint: str) -> Dict[str, Any]:
        """Make GET request to Binance API"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}", 
                headers=self.headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Binance API error: {error_text}")
                    raise BinanceAPIError(response.status, error_text)
                return await response.json()

    async def get_market_info(self, symbol: Optional[str] = None) -> MarketInfo:
        """Get market information for a symbol or market-wide data"""
        try:
            if symbol:
                # Get specific symbol data
                ticker = await self._get(f"/ticker/24hr?symbol={symbol}")
                trades = await self._get(f"/trades?symbol={symbol}&limit=5")
                
                return MarketInfo(
                    symbol=symbol,
                    data=MarketInfoData(
                        price=ticker["lastPrice"],
                        price_change=f"{ticker['priceChangePercent']}%",
                        volume24h=ticker["volume"],
                        recent_trades=[
                            Trade(
                                id=trade["id"],
                                price=trade["price"],
                                qty=trade["qty"],
                                quote_qty=trade["quoteQty"],
                                time=trade["time"],
                                is_buyer_maker=trade["isBuyerMaker"]
                            ) for trade in trades
                        ]
                    )
                )
            else:
                # Get market-wide data
                tickers = await self._get("/ticker/24hr")
                sorted_tickers = sorted(
                    tickers, 
                    key=lambda x: float(x["volume"]), 
                    reverse=True
                )
                top_pairs = [
                    MarketPair(
                        symbol=ticker["symbol"],
                        volume=ticker["volume"],
                        price_change=f"{ticker['priceChangePercent']}%"
                    ) for ticker in sorted_tickers[:10]
                ]
                
                total_volume = sum(float(ticker["volume"]) for ticker in tickers)
                
                return MarketInfo(
                    symbol="ALL",
                    data=MarketInfoData(
                        price_change="0%",  # Market-wide change not relevant
                        volume24h="0",      # Shown in individual pairs
                        top_pairs=top_pairs,
                        total_volume=total_volume
                    )
                )
                
        except BinanceAPIError:
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Connection error: {e}")
            raise ConnectionError(f"Failed to connect to Binance API: {str(e)}")
        except Exception as e:
            logger.error(f"Service error: {e}")
            raise ServiceError(f"Failed to fetch market information: {str(e)}")

    async def get_alpha(self, timeframe: str) -> AlphaAnalysis:
        """Generate alpha analysis for major pairs"""
        try:
            major_pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
            intervals = {
                "24h": "1h",
                "7d": "4h",
                "30d": "1d"
            }
            
            interval = intervals[timeframe]
            limit = 24 if timeframe == "24h" else 42 if timeframe == "7d" else 30
            
            # Fetch klines data for all pairs
            pairs_data = await asyncio.gather(*[
                self._get(f"/klines?symbol={pair}&interval={interval}&limit={limit}")
                for pair in major_pairs
            ])
            
            # Analyze patterns and volume
            insights: List[AlphaInsight] = []
            for pair_data, symbol in zip(pairs_data, major_pairs):
                volumes = [float(k[5]) for k in pair_data]  # 5th element is volume
                avg_volume = sum(volumes) / len(volumes)
                recent_volume = volumes[-1]
                
                volume_increase = ((recent_volume - avg_volume) / avg_volume) * 100
                pattern = self._detect_pattern(pair_data)
                
                if volume_increase > 10 or pattern:
                    insights.append(
                        AlphaInsight(
                            pair=symbol,
                            volume_increase=volume_increase,
                            pattern=pattern
                        )
                    )
            
            return AlphaAnalysis(
                timeframe=timeframe,
                insights=insights
            )
            
        except BinanceAPIError:
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Connection error: {e}")
            raise ConnectionError(f"Failed to connect to Binance API: {str(e)}")
        except Exception as e:
            logger.error(f"Service error: {e}")
            raise ServiceError(f"Failed to generate alpha insights: {str(e)}")

    def _detect_pattern(self, klines: List[List[Any]]) -> Optional[str]:
        """Detect trading patterns in kline data"""
        closes = [float(k[4]) for k in klines]  # 4th element is close price
        opens = [float(k[1]) for k in klines]   # 1st element is open price
        
        bullish_candles = len([1 for close, open in zip(closes, opens) if close > open])
        trend = "bullish" if bullish_candles > len(klines) / 2 else "bearish"
        
        # Check for potential breakout
        recent_price = closes[-1]
        max_price = max(closes[:-1])
        breakout = recent_price > max_price * 1.02
        
        if breakout:
            return f"Potential {trend} breakout detected"
        elif abs(bullish_candles - len(klines) / 2) > len(klines) * 0.3:
            return f"Strong {trend} trend detected"
            
        return None
