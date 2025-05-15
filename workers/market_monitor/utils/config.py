import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
from pydantic_settings import BaseSettings
from pydantic import Field

logger = logging.getLogger(__name__)

def load_yaml_config(filename: str) -> Dict[str, Any]:
    """Load YAML config file"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                # Load YAML and replace env vars
                content = f.read()
                for key, value in os.environ.items():
                    content = content.replace(f"${{{key}}}", value)
                return yaml.safe_load(content)
        return {}
    except Exception as e:
        logger.error(f"Error loading config {filename}: {e}")
        return {}

class Config(BaseSettings):
    # Try multiple possible config locations
    config_dir: Path = Field(default_factory=lambda: (
        # 1. Check if CONFIG_DIR env var is set
        Path(os.environ.get("CONFIG_DIR", "")) if os.environ.get("CONFIG_DIR") else
        # 2. Check if configs exists in current directory
        Path("configs") if Path("configs").exists() else
        # 3. Check if configs exists in parent directory
        Path(__file__).parent.parent.parent.parent / "configs" if (Path(__file__).parent.parent.parent.parent / "configs").exists() else
        # 4. Default to current directory
        Path(".")
    ))
    redis: Dict[str, Any] = Field(default_factory=dict)
    mongo: Dict[str, Any] = Field(default_factory=dict)
    api: Dict[str, Any] = Field(default_factory=dict)
    notification: Dict[str, Any] = Field(default_factory=dict)
    blockchain: Dict[str, Any] = Field(default_factory=dict)
    dex_routers: Dict[str, List[str]] = Field(default_factory=dict)
    erc20_abi: List[Dict[str, Any]] = Field(default_factory=list)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info(f"Loading configs from: {self.config_dir}")
        self.redis = self._load_redis_config()
        self.mongo = self._load_mongo_config()
        self.api = self._load_api_config()
        self.notification = self._load_notification_config()
        self.blockchain = self._load_blockchain_config()
        # Set dex_routers and erc20_abi from blockchain config
        self.dex_routers = self.blockchain.get("dex_routers", {})
        self.erc20_abi = self.blockchain.get("erc20_abi", [])

    def _load_redis_config(self) -> Dict[str, Any]:
        """Load Redis configuration"""
        # Default values
        config = {
            "host": os.environ.get("REDIS_HOST", "localhost"),
            "port": int(os.environ.get("REDIS_PORT", 6379)),
            "db": int(os.environ.get("REDIS_DB", 0)),
            "password": os.environ.get("REDIS_PASSWORD"),
            "decode_responses": True,
            "socket_connect_timeout": 5.0,
            "socket_keepalive": True
        }

        # Load from main config file
        file_config = load_yaml_config(self.config_dir / 'redis.yaml')
        if file_config and "connection" in file_config:
            conn = file_config["connection"]
            config.update({
                "host": conn.get("host", config["host"]),
                "port": int(conn.get("port", config["port"])),
                "password": conn.get("password", config["password"]),
                "decode_responses": conn.get("decode_responses", config["decode_responses"]),
                "socket_connect_timeout": conn.get("socket_connect_timeout", config["socket_connect_timeout"]),
                "socket_keepalive": conn.get("socket_keepalive", config["socket_keepalive"])
            })
            
            # Update DB number if specified
            if "db" in file_config:
                config["db"] = int(file_config["db"])

        return config

    def _load_mongo_config(self) -> Dict[str, Any]:
        """Load MongoDB configuration"""
        # Default values
        config = {
            "url": os.environ.get("MONGO_URI", "mongodb://localhost:27017"),
            "db": os.environ.get("MONGO_DB", "market_monitor")
        }

        # Load from main config file
        file_config = load_yaml_config(self.config_dir / 'mongo.yaml')
        if file_config:
            # Update connection settings
            if "connection" in file_config:
                conn = file_config["connection"]
                if "url" in conn:
                    config["url"] = conn["url"]
                elif "host" in conn:
                    config["url"] = conn["host"]
            
            # Update database name
            if "db_name" in file_config:
                config["db"] = file_config["db_name"]

        return config

    def _load_api_config(self) -> Dict[str, Any]:
        """Load API configurations"""
        # Default values
        config = {
            "root_path": "/api",
            "coingecko": {
                "url": os.environ.get("COINGECKO_API_URL", "https://api.coingecko.com/api/v3"),
                "api_key": os.environ.get("COINGECKO_API_KEY"),
                "timeout": 5
            },
            "alert": {
                "url": os.environ.get("ALERT_API_URL", "http://45.32.111.45:5000/alert"),
                "timeout": 5,
                "interval": int(os.environ.get("ALERT_CHECK_INTERVAL", 60))
            }
        }

        # Load from main config file
        file_config = load_yaml_config(self.config_dir / 'api.yaml')
        if file_config:
            # Update recursively preserving env var overrides
            def update_config(base: Dict, update: Dict):
                for k, v in update.items():
                    if isinstance(v, dict) and k in base:
                        update_config(base[k], v)
                    else:
                        base[k] = v
            update_config(config, file_config)

        return config

    def _load_notification_config(self) -> Dict[str, Any]:
        """Load notification configuration"""
        # Default values
        config = {
            "rate_limits": {
                "telegram": {"max_per_minute": 30},
                "web": {"max_per_minute": 100},
                "discord": {"max_per_minute": 50}
            },
            "retry": {
                "max_retries": 3,
                "retry_delay": 5  # seconds
            },
            "telegram": {
                "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN"),
                "timeout": 30,
                "parse_mode": "HTML"
            }
        }

        # Load from main config file
        file_config = load_yaml_config(self.config_dir / 'notification.yaml')
        if file_config:
            # Update recursively preserving env var overrides
            def update_config(base: Dict, update: Dict):
                for k, v in update.items():
                    if isinstance(v, dict) and k in base:
                        update_config(base[k], v)
                    else:
                        base[k] = v
            update_config(config, file_config)

        return config

    def _load_blockchain_config(self) -> Dict[str, Any]:
        """Load blockchain configuration"""
        # Default values
        config = {
            "connection": {
                "ethereum": {
                    "rpc_url": os.environ.get("ETH_RPC_URL", "https://eth-mainnet.g.alchemy.com/v2/YOUR-API-KEY"),
                    "ws_url": os.environ.get("ETH_WS_URL"),
                    "chain_id": 1,
                    "native_symbol": "ETH"
                },
                "bsc": {
                    "rpc_url": os.environ.get("BSC_RPC_URL", "https://bsc-dataseed.binance.org/"),
                    "ws_url": os.environ.get("BSC_WS_URL"),
                    "chain_id": 56,
                    "native_symbol": "BNB"
                },
                "base": {
                    "rpc_url": os.environ.get("BASE_RPC_URL", "https://mainnet.base.org"),
                    "ws_url": os.environ.get("BASE_WS_URL"),
                    "chain_id": 8453,
                    "native_symbol": "ETH"
                },
                "solana": {
                    "rpc_url": os.environ.get("SOL_RPC_URL", "https://api.mainnet-beta.solana.com"),
                    "ws_url": os.environ.get("SOL_WS_URL"),
                    "native_symbol": "SOL"
                }
            },
            "settings": {
                "block_cache_size": int(os.environ.get("BLOCK_CACHE_SIZE", "1000")),
                "tx_cache_size": int(os.environ.get("TX_CACHE_SIZE", "10000")),
                "watch_interval": int(os.environ.get("WATCH_INTERVAL", "30")),
                "max_blocks_per_request": int(os.environ.get("MAX_BLOCKS_PER_REQUEST", "100")),
                "retry": {
                    "max_retries": int(os.environ.get("BLOCKCHAIN_MAX_RETRIES", "3")),
                    "retry_delay": int(os.environ.get("BLOCKCHAIN_RETRY_DELAY", "5"))
                }
            },
            "dex_routers": {
                "ethereum": [
                    "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap V2 Router
                    "0xE592427A0AEce92De3Edee1F18E0157C05861564",  # Uniswap V3 Router
                    "0x1111111254EEB25477B68fb85Ed929f73A960582"   # 1inch Router
                ],
                "bsc": [
                    "0x10ED43C718714eb63d5aA57B78B54704E256024E",  # PancakeSwap Router
                    "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4"   # PancakeSwap V3 Router
                ],
                "base": [
                    "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6",  # BaseSwap Router
                    "0x327Df1E6de05895d2ab08513aaDD9313Fe505D86"   # BaseSwap V3 Router
                ]
            },
            "erc20_abi": [
                {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
                {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
                {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"}
            ]
        }

        # Load from main config file
        file_config = load_yaml_config(self.config_dir / 'blockchain.yaml')
        if file_config:
            # Update recursively preserving env var overrides
            def update_config(base: Dict, update: Dict):
                for k, v in update.items():
                    if isinstance(v, dict) and k in base:
                        update_config(base[k], v)
                    else:
                        base[k] = v
            update_config(config, file_config)

        return config

    def get_redis_url(self) -> str:
        """Get Redis connection URL"""
        password = f":{self.redis['password']}@" if self.redis.get("password") else ""
        return f"redis://{password}{self.redis['host']}:{self.redis['port']}/{self.redis['db']}"

    def get_mongo_url(self) -> str:
        """Get MongoDB connection URL"""
        return self.mongo["url"]

    def get_mongo_db(self) -> str:
        """Get MongoDB database name"""
        return self.mongo["db"]

    def get_coingecko_url(self) -> str:
        """Get CoinGecko API URL"""
        return self.api["coingecko"]["url"]
    
    def get_coingecko_api_key(self) -> str:
        """Get CoinGecko API URL"""
        return self.api["coingecko"]["api_key"]

    def get_airdrop_alert_url(self) -> str:
        """Get Airdrop API URL"""
        return self.api.get("airdrop", {}).get("url", "http://localhost:5000")
    
    def get_airdrop_alert_timeout(self) -> int:
        """Get Airdrop Alert timeout"""
        return self.api.get("airdrop", {}).get("timeout", 5)

    def get_alert_url(self) -> str:
        """Get Alert API URL"""
        return self.api["alert"]["url"]

    def get_alert_interval(self) -> int:
        """Get Alert check interval in seconds"""
        return self.api["alert"].get("interval", 60)

    def get_rpc_url(self, chain: str) -> str:
        """Get RPC URL for a specific chain"""
        return self.blockchain["connection"][chain.lower()]["rpc_url"]

    def get_ws_url(self, chain: str) -> Optional[str]:
        """Get WebSocket URL for a specific chain"""
        return self.blockchain["connection"][chain.lower()].get("ws_url")

    def get_chain_id(self, chain: str) -> int:
        """Get chain ID for a specific chain"""
        return self.blockchain["connection"][chain.lower()]["chain_id"]

    def get_scan_url(self, chain: str) -> str:
        """Get scan URL for a specific chain"""
        return self.blockchain["connection"][chain.lower()]["scan_url"]

    def get_blockchain_settings(self) -> Dict[str, Any]:
        """Get blockchain settings"""
        return self.blockchain["settings"]

    def get_native_symbol(self, chain: str) -> str:
        """Get native token symbol for a specific chain"""
        return self.blockchain["connection"][chain.lower()]["native_symbol"]

def load_yaml_config(file_path: Path) -> Dict:
    """Load YAML configuration file"""
    try:
        if file_path.exists():
            with open(file_path, 'r') as f:
                return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config file {file_path}: {e}")
    return {}

# Create global config instance
_config = Config()

def get_config() -> Config:
    """Get global config instance"""
    return _config
