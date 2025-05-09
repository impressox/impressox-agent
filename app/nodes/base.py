import json
import time
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import (
    SystemMessage,
    AIMessage,
    ToolMessage,
    HumanMessage,
)

from langchain_openai import ChatOpenAI

from app.state.agent import AgentState
from app.utils.time_util import get_current_time, get_utc_time_info
from app.configs import app_configs
from app.core.system_prompt_manager import system_prompt_manager


def get_system_config(config):
    sys_config = {}
    utc_info = get_utc_time_info()
    configuration = config.get("configurable", {})
    sys_config["user_name"] = configuration.get("user_name", "")
    sys_config["user_full_name"] = configuration.get("user_full_name", "")
    sys_config["day_name"] = configuration.get("day_name", utc_info["day_name"])
    sys_config["utc_date"] = configuration.get("utc_date", utc_info["utc_date"])
    sys_config["utc_time"] = configuration.get("utc_time", utc_info["utc_time"])
    sys_config["gender"] = configuration.get("gender", "")
    sys_config["x_birthdate"] = configuration.get("x_birthdate", "")
    sys_config["current_time"] = configuration.get("current_time", get_current_time())
    sys_config["this_sunday"] = configuration.get("this_sunday", "")
    sys_config["this_monday"] = configuration.get("this_monday", "")
    sys_config["x_culture"] = configuration.get("x_culture", "vi")
    return sys_config


class BaseNode:
    def __init__(self, name: str, model_config_key: str, tools=None):
        self.name = name
        self.model_config_key = model_config_key
        llm_config = app_configs.get_llm_config()
        self.model = self._get_model(llm_config[model_config_key], tools)

        if tools:
            self.tools = tools
            self.tool_node = ToolNode(tools)

    def configure_tools(self, tools):
        """Update tools and re-bind model."""
        if not tools:
            return
        llm_config = app_configs.get_llm_config()
        self.model = self._get_model(llm_config[self.model_config_key], tools)
        self.tools = tools
        self.tool_node = ToolNode(tools)

    def should_continue(self, state):
        messages = state.get("messages", [])
        if not messages:
            return "end"
        last_message = messages[-1]
        return "continue" if getattr(last_message, "tool_calls", None) else "end"

    def call_model(self, state: AgentState, config: RunnableConfig):
        messages = state.get("messages", [])
        if not messages:
            raise ValueError("AgentState.messages is empty.")

        last_message = messages[-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return state

        sys_config = get_system_config(config)
        system_prompt = system_prompt_manager.get_prompt(self.name)
        if not system_prompt:
            raise ValueError(f"[PromptError] System prompt for node '{self.name}' not found.")

        # Inject prompt and invoke model
        formatted_prompt = system_prompt.format(**sys_config)
        full_messages = [SystemMessage(formatted_prompt)] + messages
        response = self.model.invoke(full_messages)

        # Deduplicate tool calls if present
        if getattr(response, "tool_calls", None):
            response.tool_calls = self._dedupe_tool_calls(response.tool_calls)

        return {"messages": [response]}

    def _get_model(self, config: dict, tools: list):
        if not config:
            raise ValueError("Model config is not provided.")
        model = ChatOpenAI(
            base_url=config["base_url"],
            api_key=config["api_key"],
            model=config["model"],
            temperature=config["temperature"],
            max_retries=config["max_retries"],
            stream_usage=True,
        )
        return model.bind_tools(tools) if tools else model

    def _dedupe_tool_calls(self, tool_calls):
        deduped = []
        seen_keys = set()

        for tool_call in reversed(tool_calls):
            key = tool_call["name"] + str(tool_call["args"])
            if key not in seen_keys:
                args = {
                    k: v.replace("29/02/2025", "28/02/2025")
                         .replace("29/02/2023", "28/02/2023")
                         .replace("29/02/2026", "28/02/2026")
                    if isinstance(v, str) else v
                    for k, v in tool_call["args"].items()
                }
                tool_call["args"] = args
                seen_keys.add(key)
                deduped.append(tool_call)

        return deduped
