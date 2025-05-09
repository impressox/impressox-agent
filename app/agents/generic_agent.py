from app.agents.base_agent import BaseAgent
from app.constants import NodeName

class GenericAgent(BaseAgent):
    def __init__(self, node, name, config=None):
        self.node = node
        self.call_model = self.node.call_model
        self.should_continue = self.node.should_continue
        self.graph = None
        super().__init__(name, config)


from app.agents.agent_factory import agent_factory
from app.nodes import *

# Register all node tại đây
for key, value in NodeName.__dict__.items():
    if not key.startswith('__') and isinstance(value, str):
        node = globals().get(value)
        if node:
            agent_factory.register_agent(
                value,
                lambda config=None, node=node, node_name=value: GenericAgent(node, name=node_name, config=config)
            )
        else:
            print(f"Node {value} not found in globals()")
            continue
        print(f"Registered agent for node: {value}")
