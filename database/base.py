"""
数据库抽象基类
定义数据库操作的统一接口，方便后期切换 MySQL 等其他数据库
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from .models import Bot, BotConfig, Conversation, KeywordReply


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
    async def get_bot_by_telegram_id(self, telegram_bot_id: int) -> Optional[Bot]:
        """根据Telegram Bot ID获取Bot记录"""
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

    @abstractmethod
    async def update_bot_token(self, bot_id: int, new_token: str):
        """更新Bot的Token（Managed Bot Token 变更时使用）"""
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

    # ==================== KeywordReply 操作 ====================
    @abstractmethod
    async def add_keyword_reply(self, kw: KeywordReply) -> int:
        """添加关键词回复规则"""
        pass

    @abstractmethod
    async def get_keyword_replies(self, bot_id: int) -> list:
        """获取Bot的所有关键词回复规则"""
        pass

    @abstractmethod
    async def get_enabled_keyword_replies(self, bot_id: int) -> list:
        """获取Bot的已启用关键词回复规则"""
        pass

    @abstractmethod
    async def delete_keyword_reply(self, reply_id: int) -> bool:
        """删除关键词回复规则"""
        pass

    @abstractmethod
    async def toggle_keyword_reply(self, reply_id: int, enabled: bool) -> bool:
        """启用/禁用关键词回复规则"""
        pass

    # ==================== Pending Managed Bot 操作 ====================
    async def set_pending_managed_bot(self, owner_id: int, bot_username: str, bot_name: str):
        """存储待处理的 Managed Bot 信息（用户点击创建链接后临时保存）"""
        pass

    async def get_pending_managed_bot(self, owner_id: int, bot_username: str):
        """获取待处理的 Managed Bot 信息"""
        return None

    async def delete_pending_managed_bot(self, owner_id: int, bot_username: str):
        """删除待处理的 Managed Bot 信息"""
        pass
