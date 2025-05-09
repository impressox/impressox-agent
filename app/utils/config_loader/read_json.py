import json
from abc import ABC
from pathlib import Path

# from src.utils.config import settings
from app.utils.config_loader.config_interface import ConfigReaderInterface
# from src.utils.config_loader.serializer import Struct


class JsonConfigReader(ConfigReaderInterface, ABC):

    def __init__(self):
        super(JsonConfigReader, self).__init__()

    def read_config_from_file(self, conf_path: str):
        # conf_path = Path(__file__).joinpath(settings.APP_CONFIG.SETTINGS_DIR, config_filename)
        with open(conf_path) as file:
            config = json.load(file)
        # config_object = Struct(**config)
        return config
