"""
权限校验插件
仅允许 Bot 的 owner 使用
"""
import logging
from aiogram import Bot
from aiogram.types import Message

from .base import BasePlugin, PluginResult, PluginContext

logger = logging.getLogger(__name__)


class AuthPlugin(BasePlugin):
    """
    权限校验插件（优先级最高）
    
    标记消息发送者是否为 Bot 的 owner。
    非 owner 的消息也会放行，但会设置 is_owner=False，
    由后续插件（转发、AI等）自行处理。
    """
    name = "auth"
    priority = 1  # 最高优先级

    async def on_message(
        self,
        bot: Bot,
        message: Message,
        context: PluginContext,
    ) -> PluginResult:
        bot_record = context.bot_record
        if not bot_record:
            logger.warning("AuthPlugin: 无 bot_record，跳过消息")
            return PluginResult(stop=True)

        user_id = message.from_user.id if message.from_user else 0
        is_owner = (user_id == bot_record.owner_id)

        # 设置上下文标记
        context.user_id = user_id
        context.set("is_owner", is_owner)

        if not is_owner:
            logger.debug(
                f"AuthPlugin: 用户 {user_id} 不是 bot @{bot_record.bot_username} 的 owner"
            )

        # 放行所有消息（不阻断），由后续插件自行判断
        return PluginResult()
