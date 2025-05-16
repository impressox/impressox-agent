import aiohttp
import logging
import asyncio
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),  # Thử tối đa 3 lần
    wait=wait_exponential(multiplier=1, min=2, max=10),  # Backoff: 2s, 4s, 8s
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
)
async def call_api(
    url: str,
    method: str = "GET",
    params: Optional[Dict] = None,
    data: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    timeout: int = 30,
    session: Optional[aiohttp.ClientSession] = None
) -> Dict[str, Any]:
    """
    Async HTTP request helper with retry & exponential backoff.
    """
    close_session = False
    if session is None:
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        session = aiohttp.ClientSession(timeout=timeout_obj)
        close_session = True

    try:
        async with session.request(
            method=method,
            url=url,
            params=params,
            json=data,
            headers=headers
        ) as resp:
            status = resp.status
            try:
                resp.raise_for_status()
            except aiohttp.ClientResponseError:
                error_text = await resp.text()
                logger.error(f"[call_api] {method} {url} failed: {status} - {error_text}")
                # Các lỗi HTTP vẫn trả về, không raise (tenacity sẽ không retry)
                return {
                    "success": False,
                    "status": status,
                    "error": error_text
                }
            if status == 204:
                return {"success": True, "status": status, "data": None}
            try:
                result = await resp.json(content_type=None)
            except Exception:
                result = await resp.text()
            return {
                "success": True,
                "status": status,
                "data": result
            }
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.warning(f"[call_api] Network error: {e} - Retrying...")
        raise  # raise lại để tenacity tự retry
    except Exception as e:
        logger.error(f"[call_api] Unknown error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        if close_session:
            await session.close()