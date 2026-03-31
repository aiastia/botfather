"""
回复插件
统一输出层，负责将处理结果发送给用户，并保存对话记录
"""
import logging
from aiogram import Bot
from aiogram.types import Message

from .base import BasePlugin, PluginResult, PluginContext

logger = logging.getLogger(__name__)


class ReplyPlugin(BasePlugin):
    """
    回复插件（优先级最低，最后执行）
    负责将插件链的最终回复发送给用户
    同时处理对话历史的保存
    """
    name = "reply"
    priority = 99  # 最后执行

    # 数据库实例（由 BotManager 注入）
    db = None

    async def on_message(
        self,
        bot: Bot,
        message: Message,
        context: PluginContext,
    ) -> PluginResult:
        # 处理 /clear 命令的清空标记
        if context.get("clear_history") and self.db and context.bot_record:
            await self.db.clear_conversations(
                context.bot_record.id, context.user_id
            )
            return PluginResult()

        # 如果有回复文本，发送给用户
        reply_text = context.get("pending_reply", "")
        if not reply_text:
            return PluginResult()

        try:
            # AI 回复内容不可控，使用纯文本发送避免 Markdown/HTML 解析错误
            await message.answer(reply_text)
        except Exception as e:
            logger.error(f"消息发送失败: {e}")

        # 保存对话记录到数据库
        if self.db and context.bot_record:
            user_msg = context.get("save_user_message", "")
            assistant_msg = context.get("save_assistant_message", "")

            if user_msg:
                from database.models import Conversation
                await self.db.add_conversation(
                    Conversation(
                        bot_id=context.bot_record.id,
                        user_id=context.user_id,
                        role="user",
                        content=user_msg,
                    )
                )
            if assistant_msg:
                from database.models import Conversation
                await self.db.add_conversation(
                    Conversation(
                        bot_id=context.bot_record.id,
                        user_id=context.user_id,
                        role="assistant",
                        content=assistant_msg,
                    )
                )

        return PluginResult(handled=True)