import aiohttp
import logging
from typing import Dict, Any, Optional
from workers.market_monitor.utils.config import get_config

logger = logging.getLogger(__name__)

COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

async def call_api(
    url: str,
    method: str = "GET",
    params: Optional[Dict] = None,
    data: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    timeout: int = 30
) -> Dict:
    """Make API call with error handling"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=headers,
                timeout=timeout
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "data": result
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"API call failed: {response.status} - {error_text}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {error_text}"
                    }
    except aiohttp.ClientError as e:
        logger.error(f"API call error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error in API call: {e}")
        return {
            "success": False,
            "error": str(e)
        }

class APIClient:
    def __init__(self):
        self.config = get_config()
        # ... rest of the code ...
