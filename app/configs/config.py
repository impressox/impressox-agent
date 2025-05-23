import os
from pathlib import Path
from typing import Optional, Dict, List, Any
import yaml

from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings
from app.utils import ConfigReaderInstance

class AppConfig(BaseModel):
    """Application configurations."""

    # all the directory level information defined at app config level
    # we do not want to pollute the env level config with these information
    # this can change on the basis of usage

    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    LOGS_DIR: Path = BASE_DIR.joinpath("logs")
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

class GlobalConfig(BaseSettings):
    """Global configurations."""

    # These variables will be loaded from the .env file. However, if
    # there is a shell environment variable having the same name,
    # that will take precedence.

    APP_CONFIG: AppConfig = AppConfig()

    API_NAME: Optional[str] = Field(None, env="API_NAME")
    API_DESCRIPTION: Optional[str] = Field(None, env="API_DESCRIPTION")
    API_VERSION: Optional[str] = Field(None, env="API_VERSION")
    API_DEBUG_MODE: Optional[bool] = Field(None, env="API_DEBUG_MODE")
    API_KEY: Optional[str] = Field(None, env="API_KEY")
    
    LOG_CONFIG_FILENAME: Optional[str] = Field(None, env="LOG_CONFIG_FILENAME")
    DEV_HOST: Optional[str] = Field(None, env="DEV_HOST")
    DEV_PORT: Optional[str] = Field(None, env="DEV_PORT")

    # define global variables with the Field class
    ENV_STATE: Optional[str] = Field("dev", env="ENV_STATE")

    # environment specific variables do not need the Field class
    HOST: Optional[str] = DEV_HOST
    PORT: Optional[str] = DEV_PORT
    LOG_LEVEL: Optional[str] = Field(None, env="LOG_LEVEL")
    
    # Direct URLs for development
    MONGO_URL: Optional[str] = Field(None, env="MONGO_URL")
    LANGFUSE_URL: Optional[str] = Field(None, env="LANGFUSE_URL")
    REDIS_URL: Optional[str] = Field(None, env="REDIS_URL")
    MYSQL_URL: Optional[str] = Field(None, env="MYSQL_URL")
    ELK_URL: Optional[str] = Field(None, env="ELK_URL")
    LLM_URL: Optional[str] = Field(None, env="LLM_URL")
    VECTOR_STORE_URL: Optional[str] = Field(None, env="VECTOR_STORE_URL")
    
    # Blockchain URLs
    ETHEREUM_RPC_URL: Optional[str] = Field(None, env="ETHEREUM_RPC_URL")
    BSC_RPC_URL: Optional[str] = Field(None, env="BSC_RPC_URL")
    BASE_RPC_URL: Optional[str] = Field(None, env="BASE_RPC_URL")
    SOLANA_RPC_URL: Optional[str] = Field(None, env="SOLANA_RPC_URL")
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(None, env="TELEGRAM_BOT_TOKEN")
    
    # Config files for production
    API_CONF: Dict[str, Any] = ConfigReaderInstance.yaml.read_config_from_file("configs/api.yaml")
    ELK_CONF: Dict[str, Any] = ConfigReaderInstance.yaml.read_config_from_file("configs/logging.yaml")
    LLM_CONF: Dict[str, Any] = ConfigReaderInstance.yaml.read_config_from_file("configs/llm.yaml")
    MONGO_CONF: Dict[str, Any] = ConfigReaderInstance.yaml.read_config_from_file("configs/mongo.yaml")
    REDIS_CONF: Dict[str, Any] = ConfigReaderInstance.yaml.read_config_from_file("configs/redis.yaml")
    LANGFUSE_CONF: Dict[str, Any] = ConfigReaderInstance.yaml.read_config_from_file("configs/langfuse.yaml")
    MYSQL_CONF: Dict[str, Any] = ConfigReaderInstance.yaml.read_config_from_file("configs/mysql.yaml")
    VECTOR_STORE_CONF: Dict[str, Any] = ConfigReaderInstance.yaml.read_config_from_file("configs/vector_store.yaml")
    EMBEDDER_CONF: Dict[str, Any] = ConfigReaderInstance.yaml.read_config_from_file("configs/embedder.yaml")
    BLOCKCHAIN_CONF: Dict[str, Any] = ConfigReaderInstance.yaml.read_config_from_file("configs/blockchain.yaml")

    class Config:
        """Loads the dotenv file."""
        env_file: str = ".env"
        case_sensitive: bool = True

    def get_mongo_config(self) -> Dict[str, Any]:
        """Get MongoDB configuration.
        Returns URL config in dev mode, file config in prod mode."""
        if self.MONGO_URL:
            return {"connection": {"url": self.MONGO_URL}}
        return self.MONGO_CONF

    def get_langfuse_config(self) -> Dict[str, Any]:
        """Get Langfuse configuration.
        Returns URL config in dev mode, file config in prod mode."""
        if self.LANGFUSE_URL:
            return {"url": self.LANGFUSE_URL}
        return self.LANGFUSE_CONF

    def get_redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration.
        Returns URL config in dev mode, file config in prod mode."""
        if self.REDIS_URL:
            return {"connection": {"url": self.REDIS_URL}}
        return self.REDIS_CONF

    def get_mysql_config(self) -> Dict[str, Any]:
        """Get MySQL configuration.
        Returns URL config in dev mode, file config in prod mode."""
        if self.MYSQL_URL:
            return {"connection": {"url": self.MYSQL_URL}}
        return self.MYSQL_CONF

    def get_elk_config(self) -> Dict[str, Any]:
        """Get ELK configuration.
        Returns URL config in dev mode, file config in prod mode."""
        if self.ELK_URL:
            return {"url": self.ELK_URL}
        return self.ELK_CONF

    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration.
        Returns URL config in dev mode, file config in prod mode."""
        if self.LLM_URL:
            return {"url": self.LLM_URL}
        return self.LLM_CONF

    def get_vector_store_config(self) -> Dict[str, Any]:
        """Get Vector Store configuration.
        Returns URL config in dev mode, file config in prod mode."""
        if self.VECTOR_STORE_URL:
            return {"connection": {"url": self.VECTOR_STORE_URL}}
        return self.VECTOR_STORE_CONF

    def get_embedder_config(self) -> Dict[str, Any]:
        """Get embedder configuration."""
        return self.EMBEDDER_CONF

    def get_blockchain_config(self) -> Dict[str, Any]:
        """Get blockchain configuration.
        Returns URL config in dev mode, file config in prod mode."""
        config = self.BLOCKCHAIN_CONF.copy()
        
        # Replace environment variables in dev mode
        if self.ENV_STATE == "dev":
            if self.ETHEREUM_RPC_URL:
                config["blockchain"]["ethereum"]["rpc_url"] = self.ETHEREUM_RPC_URL
            if self.BSC_RPC_URL:
                config["blockchain"]["bsc"]["rpc_url"] = self.BSC_RPC_URL
            if self.BASE_RPC_URL:
                config["blockchain"]["base"]["rpc_url"] = self.BASE_RPC_URL
            if self.SOLANA_RPC_URL:
                config["blockchain"]["solana"]["rpc_url"] = self.SOLANA_RPC_URL
            if self.TELEGRAM_BOT_TOKEN:
                config["notification"]["telegram"]["bot_token"] = self.TELEGRAM_BOT_TOKEN
                
        return config

class DevConfig(GlobalConfig):
    """Development configurations."""

    class Config:
        env_prefix: str = "DEV_"

class ProdConfig(GlobalConfig):
    """Production configurations."""

    class Config:
        env_prefix: str = "PROD_"

class FactoryConfig:
    """Returns a config instance depending on the ENV_STATE variable."""

    def __init__(self, env_state: Optional[str]):
        self.env_state = env_state

    def __call__(self):
        if self.env_state == "dev":
            return DevConfig()

        elif self.env_state == "prod":
            return ProdConfig()

app_configs = FactoryConfig(GlobalConfig().ENV_STATE)()
# print(settings.__repr__())
