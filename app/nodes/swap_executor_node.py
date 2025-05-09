from app.nodes.base import BaseNode
from app.constants import NodeName
from app.configs import app_configs

class SwapExecutorNode(BaseNode):
    def __init__(self):
        super().__init__(NodeName.SWAP_EXECUTOR, model_config_key=app_configs.LLM_CONF["node_model"]["general"])