"""
关键词自动回复插件
当用户消息匹配到预设关键词时，额外发送对应的回复内容
不阻断其他插件流程（stop=False），仅追加回复
"""
import re
import logging
from aiogram import Bot
from aiogram.types import Message

from .base import BasePlugin, PluginResult, PluginContext

logger = logging.getLogger(__name__)


class KeywordPlugin(BasePlugin):
    """
    关键词自动回复插件
    优先级 20（在命令处理之后、转发和AI之前）
    匹配时不阻断流程，额外发送关键词对应的回复
    """
    name = "keyword"
    priority = 20
    db = None  # 由 BotManager 注入

    async def on_message(
        self,
        bot: Bot,
        message: Message,
        context: PluginContext,
    ) -> PluginResult:
        if not message.text:
            return PluginResult()

        if not self.db:
            return PluginResult()

        bot_record = context.bot_record
        if not bot_record:
            return PluginResult()

        # 获取该 Bot 的已启用关键词规则
        try:
            rules = await self.db.get_enabled_keyword_replies(bot_record.id)
        except Exception as e:
            logger.error(f"获取关键词规则失败: {e}")
            return PluginResult()

        if not rules:
            return PluginResult()

        text = message.text
        matched_replies = []

        for rule in rules:
            try:
                if rule.is_regex:
                    # 正则匹配
                    if re.search(rule.keyword, text, re.IGNORECASE):
                        matched_replies.append(rule.reply_text)
                else:
                    # 普通关键词匹配（不区分大小写）
                    if rule.keyword.lower() in text.lower():
                        matched_replies.append(rule.reply_text)
            except re.error as e:
                logger.warning(f"关键词规则 ID={rule.id} 正则语法错误: {e}")
                continue
            except Exception as e:
                logger.error(f"关键词规则 ID={rule.id} 匹配异常: {e}")
                continue

        if not matched_replies:
            return PluginResult()

        # 拼接所有匹配的回复
        reply_text = "\n\n".join(matched_replies)

        # 通过上下文传递关键词回复（不阻断流程，由 ReplyPlugin 统一发送）
        context.set("keyword_reply", reply_text)

        # 直接发送关键词回复（独立于 AI 回复）
        try:
            await message.reply(reply_text)
        except Exception as e:
            logger.error(f"发送关键词回复失败: {e}")

        return PluginResult(handled=False)