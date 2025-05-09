from typing import Dict
from app.prompts import *
from app.constants import NodeName


class SystemPromptManager:
    """System prompt manager with node-based resolution and fallback."""

    def __init__(self):
        self._base_prompts: Dict[str, str] = {}
        self._load_base_prompts()

    def _load_base_prompts(self):
        """
        Load all system prompts from the src/prompts module.
        Expecting global variables like: general_node_system_prompt, etc.
        """
        for key, value in NodeName.__dict__.items():
            if not key.startswith('__') and isinstance(value, str):
                prompt_var_name = f"{value}_system_prompt"  # e.g., general_node_system_prompt
                prompt = globals().get(prompt_var_name)
                if prompt:
                    self._base_prompts[value] = prompt
                else:
                    raise ValueError(f"System prompt for node '{value}' not found. Expected: '{prompt_var_name}'")

    def get_prompt(self, node_name: str) -> str | None:
        """
        Trả về system prompt tương ứng với node.
        """
        if node_name in self._base_prompts:
            return self._base_prompts[node_name]

        raise ValueError(f"Node name '{node_name}' not found in system prompts.")

# Global instance
system_prompt_manager = SystemPromptManager()
