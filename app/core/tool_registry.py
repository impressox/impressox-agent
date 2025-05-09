from typing import Dict, Any, Callable, Optional
from app.constants import NodeName

class ToolRegistry:
    """Tool registry with guild-based implementations"""
    
    def __init__(self):
        self._tools: Dict[str, Dict[str, Callable]]  = {}
    
    def register(self, node_name: str, name: str):
        """
        Decorator to register a tool implementation
        Args:
            node_name: str
            name: Tool name
        """
        def decorator(func: Callable):    
            def add_func_to_tool(node_name: str, name: str, func: Callable):
                if node_name not in self._tools:
                    self._tools[node_name] = {}
                if name not in self._tools[node_name]:
                    self._tools[node_name][name] = func

            if node_name == "*":          
                for key, value in NodeName.__dict__.items():
                    if not key.startswith('__') and isinstance(value, str):
                        add_func_to_tool(value, name, func)
            else:
                add_func_to_tool(node_name, name, func)
            
            return func
        return decorator
    
    def get_tools(self, node_name: str) -> Dict[str, Callable]:
        """
        Get all tool implementations based on node name
        First checks guild-specific implementations, then falls back to default
        """

        # Get tenant-specific implementations
        node_tools = self._tools.get(node_name, {})
        # Convert tools to list of Tool Dic 
        tools_list = []
        for name, func in node_tools.items():
            tools_list.append(func)
        # Fallback to default implementation
        return tools_list

    def get_tool(self, node_name: str, name: str) -> Optional[Callable]:
        """
        Get tool implementation based on tenant type
        First checks guild-specific implementations, then falls back to default
        """
        
        # Try to get tenant-specific implementation
        node_tools = self._tools.get(node_name, {})
        if name in node_tools:
            return node_tools[node_name][name]
            
        # Fallback to default implementation
        return {}

# Global registry instance
tool_registry = ToolRegistry()

def register_tool(node_name: str, name: str):
    """Convenience decorator to register tools"""
    return tool_registry.register(node_name, name)