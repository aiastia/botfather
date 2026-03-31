"""
AI 对话插件
接入 OpenAI 兼容接口，支持自定义 API URL
"""
import logging
from aiogram import Bot
from aiogram.types import Message
from openai import AsyncOpenAI

from .base import BasePlugin, PluginResult, PluginContext
from config.settings import settings

logger = logging.getLogger(__name__)


class AIPlugin(BasePlugin):
    """
    AI 对话插件
    支持 OpenAI 兼容接口，每个 Bot 可独立配置 API Key 和 URL
    """
    name = "ai"
    priority = 50

    # 全局 OpenAI 客户端缓存（按 api_key+base_url 缓存）
    _clients: dict = {}

    def _get_client(self, api_key: str, base_url: str) -> AsyncOpenAI:
        """获取或创建 OpenAI 客户端"""
        cache_key = f"{api_key}:{base_url}"
        if cache_key not in self._clients:
            self._clients[cache_key] = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
        return self._clients[cache_key]

    async def on_message(
        self,
        bot: Bot,
        message: Message,
        context: PluginContext,
    ) -> PluginResult:
        # 仅处理文本消息
        if not message.text or message.text.startswith("/"):
            return PluginResult()

        bot_config = context.bot_config
        bot_record = context.bot_record

        # 检查 AI 是否启用
        if not bot_config or not bot_config.ai_enabled:
            return PluginResult(
                stop=True,
                reply_text="⚠️ AI 功能未启用。请在主Bot中使用 /config 命令开启。",
                handled=True,
            )

        # 获取 API 配置（Bot专属 > 全局配置）
        api_key = bot_config.ai_api_key or settings.AI_API_KEY
        api_base = bot_config.ai_api_base_url or settings.AI_API_BASE_URL
        model = bot_config.ai_model or settings.AI_MODEL
        temperature = bot_config.ai_temperature or settings.AI_TEMPERATURE
        max_tokens = bot_config.ai_max_tokens or settings.AI_MAX_TOKENS
        system_prompt = bot_config.ai_system_prompt or "你是一个友好的AI助手。"

        if not api_key:
            return PluginResult(
                stop=True,
                reply_text="❌ AI API Key 未配置。请联系管理员。",
                handled=True,
            )

        try:
            client = self._get_client(api_key, api_base)

            # 构建消息列表
            messages = [{"role": "system", "content": system_prompt}]

            # 加载对话历史（通过 context 获取）
            history = context.get("conversation_history", [])
            messages.extend(history)

            # 添加当前消息
            user_text = message.text
            messages.append({"role": "user", "content": user_text})

            # 调用 AI API
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            ai_reply = response.choices[0].message.content

            # 通过上下文传递对话记录（供后续保存）
            context.set("save_user_message", user_text)
            context.set("save_assistant_message", ai_reply)

            return PluginResult(
                reply_text=ai_reply,
                handled=True,
            )

        except Exception as e:
            logger.error(f"AI 调用失败: {e}", exc_info=True)
            return PluginResult(
                stop=True,
                reply_text=f"❌ AI 调用失败：{str(e)[:100]}",
                handled=True,
            )