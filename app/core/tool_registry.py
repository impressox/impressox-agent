from typing import Dict, Callable, Optional, List
from langchain_core.tools import Tool, BaseTool
from app.constants import NodeName

class ToolRegistry:
    """Tool registry with node-based implementation"""
    
    def __init__(self):
        self._tools: Dict[str, Dict[str, BaseTool]] = {}

    def register(self, node_name: str, name: str):
        """
        Decorator to register a LangChain-compatible tool instance
        """
        def decorator(func: Callable):
            # Ensure the function is wrapped into a LangChain Tool
            if not isinstance(func, BaseTool):
                tool = Tool.from_function(func)
            else:
                tool = func

            def add_tool_to_node(node: str, tool_name: str, tool_obj: BaseTool):
                if node not in self._tools:
                    self._tools[node] = {}
                self._tools[node][tool_name] = tool_obj

            if node_name == "*":
                for key, value in NodeName.__dict__.items():
                    if not key.startswith('__') and isinstance(value, str):
                        add_tool_to_node(value, name, tool)
            else:
                add_tool_to_node(node_name, name, tool)

            return tool  # return the tool instance (important for LangChain)
        return decorator

    def get_tool(self, node_name: str, name: str) -> Optional[BaseTool]:
        node_tools = self._tools.get(node_name, {})
        return node_tools.get(name)

    def get_tools(self, node_name: str) -> List[BaseTool]:
        """
        Return list of LangChain BaseTool objects (safe to pass to ToolNode)
        """
        node_tools = self._tools.get(node_name, {})
        return list(node_tools.values())

# Global singleton
tool_registry = ToolRegistry()

def register_tool(node_name: str, name: str):
    return tool_registry.register(node_name, name)
