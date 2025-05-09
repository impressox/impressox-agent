from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import time
from datetime import datetime
from pydantic import BaseModel, Field

class WatchType(str, Enum):
    TOKEN = "token"
    WALLET = "wallet"
    CONTRACT = "contract"

class NotifyChannel(str, Enum):
    TELEGRAM = "telegram"
    WEB = "web"
    DISCORD = "discord"

class Rule(BaseModel):
    rule_id: str
    user_id: str
    watch_type: WatchType
    target: List[str]
    condition: Optional[Dict] = None
    notify_channel: NotifyChannel
    notify_id: str
    target_data: Optional[Dict] = None
    metadata: Optional[Dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "active"

    @classmethod
    def from_dict(cls, data: Dict) -> 'Rule':
        """Create Rule instance from dictionary"""
        if isinstance(data.get("watch_type"), str):
            data["watch_type"] = WatchType(data["watch_type"])
        if isinstance(data.get("notify_channel"), str):
            data["notify_channel"] = NotifyChannel(data["notify_channel"])
        # Convert notify_id to string if it's not already
        if "notify_id" in data and not isinstance(data["notify_id"], str):
            data["notify_id"] = str(data["notify_id"])
        return cls(**data)

    def to_dict(self) -> Dict:
        """Convert Rule instance to dictionary"""
        return self.dict()

@dataclass
class RuleMatch:
    rule: Rule
    match_data: Dict[str, Any]
    matched_at: float = time.time()

    def to_dict(self) -> Dict:
        return {
            "rule": self.rule.to_dict(),
            "match_data": self.match_data,
            "matched_at": self.matched_at
        }

class Notification(BaseModel):
    user: str
    channel: NotifyChannel
    message: str
    metadata: Optional[Dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"

    def to_dict(self) -> Dict:
        """Convert Notification instance to dictionary"""
        return {
            "user": self.user,
            "channel": self.channel.value,
            "message": self.message,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "status": self.status
        }
