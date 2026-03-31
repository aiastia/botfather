"""
命令处理插件
处理子Bot的 /start, /help, /clear 等基础命令
"""
import logging
from aiogram import Bot
from aiogram.types import Message

from .base import BasePlugin, PluginResult, PluginContext

logger = logging.getLogger(__name__)


class CommandPlugin(BasePlugin):
    """
    命令处理插件
    处理子Bot的基础命令，优先级仅次于权限插件
    """
    name = "command"
    priority = 10

    async def on_message(
        self,
        bot: Bot,
        message: Message,
        context: PluginContext,
    ) -> PluginResult:
        if not message.text or not message.text.startswith("/"):
            return PluginResult()

        command = message.text.split()[0].lower()
        bot_record = context.bot_record

        # /start 命令
        if command == "/start":
            safe_name = bot_record.bot_firstname
            welcome_text = (
                f"👋 你好！我是 <b>{safe_name}</b>\n\n"
                f"我是 AI 私聊助手，你可以直接给我发消息。\n\n"
                f"📝 可用命令：\n"
                f"/start - 查看欢迎信息\n"
                f"/help - 查看帮助\n"
                f"/clear - 清空对话记忆\n"
                f"/config - 查看当前配置"
            )
            return PluginResult(stop=True, reply_text=welcome_text, handled=True)

        # /help 命令
        elif command == "/help":
            help_text = (
                "📖 <b>使用帮助</b>\n\n"
                "直接给我发送任何消息，我会使用 AI 回复你。\n"
                "同时你的消息会转发给 Bot 主人。\n\n"
                "📌 命令列表：\n"
                "/start - 欢迎信息\n"
                "/help - 帮助信息\n"
                "/clear - 清空对话记忆\n"
                "/config - 查看配置\n\n"
                "💡 Bot 主人可通过主控Bot配置 AI 参数。"
            )
            return PluginResult(stop=True, reply_text=help_text, handled=True)

        # /clear 命令 - 清空对话历史
        elif command == "/clear":
            # 通过上下文传递清空标记
            context.set("clear_history", True)
            return PluginResult(
                stop=True,
                reply_text="🗑️ 对话记忆已清空！",
                handled=True,
            )

        # /config 命令 - 查看当前配置
        elif command == "/config":
            bot_config = context.bot_config
            if bot_config:
                config_text = (
                    "⚙️ <b>当前配置</b>\n\n"
                    f"🤖 AI 模型: <code>{bot_config.ai_model}</code>\n"
                    f"🌡️ 温度: {bot_config.ai_temperature}\n"
                    f"📏 最大Token: {bot_config.ai_max_tokens}\n"
                    f"💡 AI 状态: {'✅ 开启' if bot_config.ai_enabled else '❌ 关闭'}\n"
                    f"📝 系统提示词: {bot_config.ai_system_prompt[:50]}..."
                )
            else:
                config_text = "⚠️ 暂无配置信息"
            return PluginResult(stop=True, reply_text=config_text, handled=True)

        return PluginResult()