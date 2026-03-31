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
    
    检查消息发送者是否为 Bot 的 owner。
    如果不是 owner，则终止后续插件执行并忽略消息。
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

        if user_id != bot_record.owner_id:
            # 非 owner，忽略消息
            logger.debug(
                f"AuthPlugin: 用户 {user_id} 不是 bot @{bot_record.bot_username} 的 owner ({bot_record.owner_id})，已忽略"
            )
            return PluginResult(stop=True)

        # 是 owner，放行
        context.user_id = user_id
        return PluginResult()