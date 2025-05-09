# services/core_api.py

import requests
from clients.config import CORE_API_URL, TIMEOUT, STREAM_TIMEOUT
import aiohttp
import httpx
from clients.telegram.utils.logger import logger

async def send_message_to_core(session_id: str, message: str, configurable_dict: dict):
    """
    Send message to core API and get response
    """
    try:
        payload = {
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            },
            "config": {
                "configurable": configurable_dict
            }
        }

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{CORE_API_URL.format(session_id=session_id)}",
                json=payload
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"HTTP error occurred: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error sending message to core: {e}")
        return {"error": str(e)}

async def send_message_to_core_streaming(session_id: str, user_message: str, configurable: dict):
    url = f"{CORE_API_URL.format(session_id=session_id)}/stream"
    payload = {
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        },
        "config": {
            "configurable": configurable
        }
    }

    timeout = aiohttp.ClientTimeout(total=STREAM_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                raise Exception(f"Core stream error: {resp.status}")
            async for line in resp.content:
                text = line.decode().strip()
                if text.startswith("data:"):
                    yield text[5:].strip()