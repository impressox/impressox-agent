from app.nodes.base import BaseNode
from app.constants import NodeName
from app.configs import app_configs

class GeneralNode(BaseNode):
    def __init__(self):
        super().__init__(NodeName.GENERAL_NODE, model_config_key=app_configs.LLM_CONF["node_model"]["general"])
