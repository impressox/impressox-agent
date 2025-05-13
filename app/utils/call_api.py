import httpx
import time
import json
import asyncio
from urllib.parse import urlparse
from aiobreaker import CircuitBreaker

# === Registry chứa breaker riêng cho từng API endpoint ===
breaker_registry = {}

def get_breaker(api_key: str, fail_max=3, timeout_duration=30) -> CircuitBreaker:
    """Tạo hoặc lấy circuit breaker cho một API cụ thể"""
    if api_key not in breaker_registry:
        breaker_registry[api_key] = CircuitBreaker(
            fail_max=fail_max,
            timeout_duration=timeout_duration
        )
    return breaker_registry[api_key]

async def call_api(
    url: str,
    data: dict = None,
    method: str = "POST",
    headers: dict = None,
    timeout: int = 30,
    retries: int = 3,
    retry_delay: float = 1.0,
    breaker_key: str = None  # Cho phép override nếu muốn
) -> dict:
    if method not in ["POST", "PUT", "DELETE", "GET"]:
        raise ValueError("Method must be one of: POST, PUT, DELETE, GET")
    if not url:
        raise ValueError("URL cannot be empty")

    _headers = {
        "Content-Type": "application/json",
        **(headers or {})
    }

    params = data if method == "GET" and data else None
    json_body = None if method == "GET" else data or {}

    # === Tự động tính breaker_key từ URL nếu không truyền ===
    parsed = urlparse(url)
    api_key = breaker_key or parsed.path  # Ví dụ: "/coins/ethereum/ohlc"
    breaker = get_breaker(api_key)

    last_error = None

    for attempt in range(1, retries + 1):
        try:
            async def do_request():
                st = time.time()
                async with httpx.AsyncClient(timeout=timeout) as client:
                    if method == "GET":
                        response = await client.get(url, headers=_headers, params=params)
                    elif method == "PUT":
                        response = await client.put(url, headers=_headers, json=json_body)
                    elif method == "DELETE":
                        response = await client.delete(url, headers=_headers, json=json_body)
                    else:
                        response = await client.post(url, headers=_headers, json=json_body)
                et = time.time()

                try:
                    response_data = response.json()
                except ValueError:
                    response_data = response.text

                log = {
                    "duration": round(et - st, 3),
                    "inputs": {"url": url, "headers": _headers, "data": data},
                    "outputs": {"status_code": response.status_code, "body": response_data}
                }

                if response.status_code != 200:
                    raise httpx.HTTPStatusError("Non-200 status code", request=None, response=response)

                return {"success": True, "data": response_data}

            return await breaker.call(do_request)

        except (httpx.RequestError, httpx.HTTPStatusError, Exception) as e:
            last_error = str(e)
            if attempt < retries:
                await asyncio.sleep(retry_delay * attempt)
            else:
                break

    return {
        "success": False,
        "error": f"API call to {api_key} failed after {retries} attempts: {last_error}"
    }
