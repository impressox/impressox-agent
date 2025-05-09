import httpx
import time
import json

async def call_api(
    url: str,
    data: dict = None,
    method: str = "POST",
    headers: dict = None,
    timeout: int = 30,
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

    try:
        st = time.time()
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                response = await client.get(url, headers=_headers, params=params)
            elif method == "PUT":
                response = await client.put(url, headers=_headers, json=json_body)
            elif method == "DELETE":
                response = await client.delete(url, headers=_headers, json=json_body)
            else:  # POST
                response = await client.post(url, headers=_headers, json=json_body)
        et = time.time()
    except httpx.RequestError as e:
        return {"success": False, "error": str(e)}

    try:
        response_data = response.json()
    except ValueError:
        response_data = response.text

    log = {
        "duration": round(et - st, 3),
        "inputs": {"url": url, "headers": _headers, "data": data},
        "outputs": {"status_code": response.status_code, "body": response_data}
    }
    # Uncomment to debug
    # print("=====================================", flush=True)
    # print("API CALL LOG:" + json.dumps(log, indent=4, ensure_ascii=False), flush=True)
    # print("=====================================", flush=True)

    if response.status_code != 200:
        return {
            "success": False,
            "error": response_data if isinstance(response_data, str) else response_data.get("error", "Unknown error")
        }

    return {"success": True, "data": response_data}
