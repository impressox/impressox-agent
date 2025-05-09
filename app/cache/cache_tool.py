import hashlib
import pickle
import json
import copy
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from app.cache import redis_client

def get_cache_tool(tool: str, json_data):
    """Get cached tool from Redis using the given JSON data."""
    cache_key = generate_cache_key(tool, json_data)
    tool = redis_client.get(cache_key)
    return json.loads(tool) if tool else None

def set_cache_tool(tool: str, json_data, response, ex):
    """Set cached tool in Redis using the given key and value.""" 
    cache_key = generate_cache_key(tool, json_data)
    value = json.dumps(response)
    return redis_client.set(cache_key, value, expire=ex)

def generate_cache_key(tool: str, json_data):
    """Generate a cache key based on JSON data."""
    data_str = json.dumps(json_data, sort_keys=True)
    return f"{tool}_{hashlib.sha256(data_str.encode()).hexdigest()}"


def cache_messages(state):
    state["enable_cache"] = False
    cache_key = copy.deepcopy(state["cache_key"])
    cache_age = copy.deepcopy(state["cache_age"])
    state["cache_key"] = None
    state["cache_age"] = None
    is_error = False
    cache_messages = []
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            break
        elif isinstance(message, AIMessage):
            cache_messages.append(message)
        elif isinstance(message, ToolMessage):
            data = json.loads(message.content)
            if data.get("is_error", False):
                is_error = True
                break
            cache_messages.append(message)
    if is_error:
        return state
    cache_messages.reverse()
    serialized_messages = pickle.dumps(cache_messages)
    redis_client.set(cache_key, serialized_messages, expire=cache_age)
    return state
