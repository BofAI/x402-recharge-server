"""Configuration management"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Environment
    ainft_env: str = Field(default="prod", description="Environment: prod | dev")
    tron_rpc_url: str = Field(default="")
    
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    mcp_port: int = Field(default=8001)
    log_level: str = Field(default="info")
    
    # ERC-8004
    erc8004_agent_id: Optional[str] = Field(default=None)
    agent_operator_key: Optional[str] = Field(default=None)
    
    # Service
    service_fee_trx: float = Field(default=0.0)
    rate_limit_per_minute: int = Field(default=10)

    # x402 settlement facilitator
    x402_facilitator_url: str = Field(default="https://facilitator.bankofai.io")
    facilitator_api_key: str = Field(default="")

    @property
    def network(self) -> str:
        env = self.ainft_env.lower().strip()
        if env == "dev":
            return "nile"
        if env == "prod":
            return "mainnet"
        raise ValueError(f"Invalid AINFT_ENV: {self.ainft_env}. Expected: dev | prod")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


class NetworkConfig:
    """Network configuration loader"""
    
    def __init__(self, network: str = "nile"):
        self.network = network
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load network configuration from JSON"""
        config_path = Path(__file__).parent.parent / "config" / "networks.json"
        with open(config_path, "r") as f:
            all_configs = json.load(f)
        
        if self.network not in all_configs:
            raise ValueError(f"Invalid network: {self.network}. Available: {list(all_configs.keys())}")
        
        return all_configs[self.network]
    
    @property
    def name(self) -> str:
        return self._config["name"]
    
    @property
    def rpc_url(self) -> str:
        return self._config["rpcUrl"]
    
    @property
    def explorer(self) -> str:
        return self._config["explorer"]
    
    @property
    def chain_id(self) -> str:
        return self._config["chainId"]
    
    @property
    def ainft_deposit_address(self) -> str:
        return self._config["ainftDepositAddress"]
    
    @property
    def ainft_api_url(self) -> str:
        return self._config["ainftApiUrl"]
    
    @property
    def ainft_web_url(self) -> str:
        return self._config["ainftWebUrl"]
    
    @property
    def erc8004_registry(self) -> str:
        return self._config["erc8004Registry"]
    
    @property
    def tokens(self) -> Dict[str, Any]:
        return self._config["tokens"]
    
    def get_token_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get token information by symbol"""
        return self.tokens.get(symbol.upper())
    
    def validate_token(self, symbol: str) -> bool:
        """Check if token is supported"""
        return symbol.upper() in self.tokens
    
    def get_minimum_amount(self, symbol: str) -> Optional[str]:
        """Get minimum deposit amount for token"""
        token_info = self.get_token_info(symbol)
        return token_info["minimum"] if token_info else None


# Global settings instance
settings = Settings()
network_config = NetworkConfig(settings.network)
