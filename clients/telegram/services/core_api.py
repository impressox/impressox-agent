# services/core_api.py
from clients.config import CORE_API_URL, TIMEOUT, STREAM_TIMEOUT
import aiohttp
import httpx
from clients.telegram.utils.logger import logger

async def send_message_to_core(session_id: str, message: str, configurable_dict: dict):
    """
    Send message to core API and get response
    """
    try:
        # Include replied message content if available
        replied_content = configurable_dict.get("replied_message_content")
        if replied_content:
            message = f"""context: "{replied_content}"
user: "{message}" """

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
        return {
            "error": "I apologize, but I'm having trouble connecting to my brain. Please try again in a moment.",
            "error_details": str(e)  # For logging purposes only
        }
    except Exception as e:
        logger.error(f"Error sending message to core: {e}")
        return {
            "error": "I apologize, but I encountered an unexpected error. Please try again in a moment.",
            "error_details": str(e)  # For logging purposes only
        }

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
                logger.error(f"Core stream error: {resp.status}")
                raise Exception("I apologize, but I'm having trouble processing your request. Please try again in a moment.")
            async for line in resp.content:
                text = line.decode().strip()
                if text.startswith("data:"):
                    yield text[5:].strip()