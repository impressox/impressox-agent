from abc import ABC, abstractmethod
from typing import Dict, Any, List, TypedDict, Literal
from langgraph.graph import StateGraph, END
from langchain.tools import Tool


from app.state.agent import AgentState
from app.core import tool_registry

from app.cache.check_point import get_memory_saver


class GraphConfig(TypedDict):
    model_name: Literal["openai", "anthropic", "slm-general"]

class BaseAgent(ABC):
    """Base class defining common agent interface"""

    def __init__(self, name, config):
        """Initialize agent with optional configuration"""
        self.config = config or {}
        self.name = name 
        self._setup()

    def _setup(self) -> List[Tool]:
        tools = tool_registry.get_tools(self.name)
        if not tools:
            tools = []
        if self.graph is not None:
            return
        if getattr(self.node, "tools", None):
            tools.extend(self.node.tools)
        
        if self.node.configure_tools:
            self.node.configure_tools(tools)

        if getattr(self.node, "tool_node", None) is not None:
            self.tool_node = self.node.tool_node
        else:
            self.tool_node = None
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the workflow graph for this agent, including memory and optional action tool."""

        memory = get_memory_saver()
        graph = StateGraph(AgentState, config_schema=GraphConfig)

        # Add primary agent node
        graph.add_node("agent", self.call_model)
        graph.set_entry_point("agent")

        # Check if there's a tool/action node to integrate
        if self.tool_node is not None:
            graph.add_node("action", self.tool_node)
            graph.add_conditional_edges(
                "agent",
                self.should_continue,
                {
                    "continue": "action",
                    "end": END,
                },
            )
            graph.add_edge("action", "agent")
        else:
            # If no tool node, end after first agent step
            graph.add_edge("agent", END)

        return graph.compile(checkpointer=memory)
    
    def get_graph(self) -> StateGraph:
        """Get the workflow graph for this agent"""
        return self.graph

    @classmethod
    def create(cls, **kwargs) -> 'BaseAgent':
        """Factory method to create agent instance"""
        return cls(**kwargs)
