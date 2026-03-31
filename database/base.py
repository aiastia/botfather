"""
数据库抽象基类
定义数据库操作的统一接口，方便后期切换 MySQL 等其他数据库
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from .models import Bot, BotConfig, Conversation


class DatabaseBase(ABC):
    """数据库操作抽象基类"""

    # ==================== 表初始化 ====================
    @abstractmethod
    async def init_tables(self):
        """初始化数据库表"""
        pass

    # ==================== Bot 操作 ====================
    @abstractmethod
    async def add_bot(self, bot: Bot) -> int:
        """添加Bot，返回插入的ID"""
        pass

    @abstractmethod
    async def get_bot(self, bot_id: int) -> Optional[Bot]:
        """根据ID获取Bot"""
        pass

    @abstractmethod
    async def get_bot_by_token(self, token: str) -> Optional[Bot]:
        """根据Token获取Bot"""
        pass

    @abstractmethod
    async def get_bots_by_owner(self, owner_id: int) -> List[Bot]:
        """获取用户的所有Bot"""
        pass

    @abstractmethod
    async def get_all_active_bots(self) -> List[Bot]:
        """获取所有活跃的Bot"""
        pass

    @abstractmethod
    async def update_bot_status(self, bot_id: int, status: str):
        """更新Bot状态"""
        pass

    @abstractmethod
    async def delete_bot(self, bot_id: int):
        """删除Bot（软删除）"""
        pass

    # ==================== BotConfig 操作 ====================
    @abstractmethod
    async def get_bot_config(self, bot_id: int) -> Optional[BotConfig]:
        """获取Bot配置"""
        pass

    @abstractmethod
    async def create_bot_config(self, config: BotConfig) -> int:
        """创建Bot配置"""
        pass

    @abstractmethod
    async def update_bot_config(self, config: BotConfig):
        """更新Bot配置"""
        pass

    # ==================== Conversation 操作 ====================
    @abstractmethod
    async def add_conversation(self, conv: Conversation) -> int:
        """添加对话记录"""
        pass

    @abstractmethod
    async def get_conversations(self, bot_id: int, user_id: int, limit: int = 20) -> List[Conversation]:
        """获取对话历史"""
        pass

    @abstractmethod
    async def clear_conversations(self, bot_id: int, user_id: int):
        """清空对话历史"""
        pass