from typing import Dict, Type, Callable, Union, Optional
from app.agents.base_agent import BaseAgent

AgentType = Union[Type[BaseAgent], Callable[..., BaseAgent]]

class AgentFactory:
    """Factory for registering and creating agents by intent, with auto caching using tenant in config."""

    def __init__(self):
        self._agent_types: Dict[str, AgentType] = {}
        self._agent_cache: Dict[str, BaseAgent] = {}

    def register_agent(self, intent: str, agent_source: AgentType):
        """Register an agent class or callable for a specific intent."""
        self._agent_types[intent] = agent_source

    def get_agent_source(self, intent: str) -> AgentType:
        if intent not in self._agent_types:
            raise ValueError(f"No agent registered for intent: {intent}")
        return self._agent_types[intent]

    def _build_cache_key(self, intent: str, config: Optional[dict]) -> Optional[str]:
        return f"{intent}"

    def create(
        self,
        intent: str,
        config: Optional[dict] = None,
        use_cache: bool = False,
    ) -> BaseAgent:
        """
        Create (or reuse) an agent instance for a given intent.
        - use_cache: if True, reuse same instance from cache
        """
        cache_key = self._build_cache_key(intent, config) if use_cache else None

        if use_cache:
            if not cache_key:
                raise ValueError("Cache key is required for caching.")
            if cache_key in self._agent_cache:
                return self._agent_cache[cache_key]

        agent_source = self.get_agent_source(intent)

        # Instantiate
        if callable(agent_source):
            agent = agent_source(config=config) if config else agent_source()
        else:
            agent = agent_source(config=config) if config else agent_source()

        if use_cache:
            self._agent_cache[cache_key] = agent

        return agent

# Global agent factory instance
agent_factory = AgentFactory()