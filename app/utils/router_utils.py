import json
import re
import ast
import time
import requests
import traceback
import numpy as np
from typing import List, Dict, Any
from typing import Literal
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from openai import OpenAI
from app.constants import subgraph_mapping
from app.state.agent import AgentState
from app.configs import app_configs
from app.prompts.router_prompt import router_prompt
from app.constants import NodeName

class RouterUtils:
    def __init__(self):
        """Initialize router with LLM configurations from settings"""
        llm_config = app_configs.get_llm_config()
        router_config = llm_config["router-classify"]
        self.llm_router_agent = ChatOpenAI(
            base_url=router_config["base_url"],
            api_key=router_config["api_key"],
            model=router_config["model"],
            temperature=router_config["temperature"],
            max_tokens=3,
            stream_usage=True,
        )

    def router_agent(self, state: AgentState) -> NodeName:
        """
        Route the conversation to the appropriate agent type based on context.

        Args:
            state: Agent state

        Returns:
            Destination agent type (e.g., NodeName.GENERAL_NODE)
        """
        try:
            # If subgraph_mapping is empty, raise error
            if not subgraph_mapping:
                raise ValueError("Subgraph mapping is empty. Cannot route to any agent.")
            # If subgraph_mapping has 1 item, return that item
            if len(subgraph_mapping) == 1:
                return list(subgraph_mapping.values())[0]["type"]
            # Extract messages into string format
            messages = []
            for msg in state["messages"]:
                if isinstance(msg, AIMessage) and msg.content:
                    messages.append(f"assistant: {msg.content}")
                elif isinstance(msg, HumanMessage):
                    messages.append(f"user: {msg.content}")

            chat_history = "\n".join(messages[-4:])
            prompt = router_prompt.format(chat_history=chat_history)
            
            print(f"Router prompt: {prompt}")

            # Call LLM
            response = self.llm_router_agent.invoke([("human", prompt)])
            res = response.content.strip().upper()

            # Match to known agents
            for agent_key, agent_info in subgraph_mapping.items():
                if agent_key.upper() == res:
                    return agent_info["type"]

        except Exception:
            traceback.print_exc()

        # Fallback
        return subgraph_mapping["A0"]["type"]

router_utils = RouterUtils()
