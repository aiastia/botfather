"""
数据模型定义
使用纯SQL + 字典方式，避免重度ORM依赖，方便后期切换数据库
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class Bot:
    """Bot实例模型"""
    id: Optional[int] = None
    owner_id: int = 0
    bot_token: str = ""
    bot_id: int = 0
    bot_username: str = ""
    bot_firstname: str = ""
    status: str = "active"  # active / stopped / deleted
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "bot_token": self.bot_token,
            "bot_id": self.bot_id,
            "bot_username": self.bot_username,
            "bot_firstname": self.bot_firstname,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Bot":
        return cls(
            id=row["id"],
            owner_id=row["owner_id"],
            bot_token=row["bot_token"],
            bot_id=row["bot_id"],
            bot_username=row["bot_username"],
            bot_firstname=row["bot_firstname"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class BotConfig:
    """Bot配置模型"""
    id: Optional[int] = None
    bot_id: int = 0  # 关联Bot.id
    ai_enabled: bool = False
    ai_model: str = "gpt-3.5-turbo"
    ai_temperature: float = 0.7
    ai_max_tokens: int = 2000
    ai_system_prompt: str = "你是一个友好的AI助手。"
    ai_api_key: str = ""  # 为空则使用全局配置
    ai_api_base_url: str = ""  # 为空则使用全局配置
    custom_config: str = "{}"  # JSON格式自定义配置
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "bot_id": self.bot_id,
            "ai_enabled": self.ai_enabled,
            "ai_model": self.ai_model,
            "ai_temperature": self.ai_temperature,
            "ai_max_tokens": self.ai_max_tokens,
            "ai_system_prompt": self.ai_system_prompt,
            "ai_api_key": self.ai_api_key,
            "ai_api_base_url": self.ai_api_base_url,
            "custom_config": self.custom_config,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: dict) -> "BotConfig":
        return cls(
            id=row["id"],
            bot_id=row["bot_id"],
            ai_enabled=bool(row["ai_enabled"]),
            ai_model=row["ai_model"],
            ai_temperature=row["ai_temperature"],
            ai_max_tokens=row["ai_max_tokens"],
            ai_system_prompt=row["ai_system_prompt"],
            ai_api_key=row["ai_api_key"],
            ai_api_base_url=row["ai_api_base_url"],
            custom_config=row["custom_config"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Conversation:
    """对话记录模型"""
    id: Optional[int] = None
    bot_id: int = 0  # 关联Bot.id
    user_id: int = 0
    role: str = ""  # user / assistant / system
    content: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def from_row(cls, row: dict) -> "Conversation":
        return cls(
            id=row["id"],
            bot_id=row["bot_id"],
            user_id=row["user_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )