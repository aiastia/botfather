"""
消息转发插件
将用户发给子Bot的所有消息转发给Bot主人，Bot主人可以直接回复转发消息来回复用户
支持：文本、图片、视频、表情包、转发消息等所有类型
"""
import logging
from aiogram import Bot
from aiogram.types import Message
from aiogram.enums import ParseMode

from .base import BasePlugin, PluginResult, PluginContext

logger = logging.getLogger(__name__)


class ForwardPlugin(BasePlugin):
    """
    消息转发插件（优先级介于 command 和 ai 之间）
    
    功能：
    - 用户发给Bot的消息 → 转发给Bot主人
    - Bot主人回复转发消息 → 转发回原用户
    - 支持所有消息类型（文本、图片、视频、贴纸等）
    """
    name = "forward"
    priority = 30  # 在 auth(5) 和 command(10) 之后，ai(50) 之前

    # Bot主人待处理的消息映射
    # key: Bot主人chat_id:message_id, value: (user_id, user_message_id, target_bot_id)
    _pending_replies: dict = {}

    async def on_message(
        self,
        bot: Bot,
        message: Message,
        context: PluginContext,
    ) -> PluginResult:
        if not message.from_user:
            return PluginResult()

        bot_record = context.bot_record
        owner_id = bot_record.owner_id
        user_id = message.from_user.id
        is_owner = (user_id == owner_id)

        if is_owner:
            # Bot主人回复 → 转发给用户
            return await self._handle_owner_reply(bot, message, owner_id)
        else:
            # 普通用户 → 转发给Bot主人
            return await self._handle_user_message(bot, message, owner_id, user_id, context)

    async def _handle_user_message(
        self,
        bot: Bot,
        message: Message,
        owner_id: int,
        user_id: int,
        context: PluginContext,
    ) -> PluginResult:
        """将用户消息转发给Bot主人"""
        try:
            user_name = message.from_user.full_name
            username = message.from_user.username or ""
            
            # 转发原始消息给Bot主人
            forwarded = await bot.forward_message(
                chat_id=owner_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )

            # 发送用户信息头
            safe_name = user_name.replace("_", "\\_")
            header = (
                f"📨 **来自 @{username}** (ID: `{user_id}`)\n"
                f"👤 {safe_name}\n"
                f"───────────────\n"
                f"💬 回复此消息即可回复该用户"
            )
            info_msg = await bot.send_message(
                chat_id=owner_id,
                text=header,
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=forwarded.message_id,
            )

            # 记录映射关系，使用 info_msg 的 message_id 作为key
            self._pending_replies[f"{owner_id}:{forwarded.message_id}"] = {
                "user_id": user_id,
                "user_name": user_name,
                "username": username,
            }
            # 也记录回复消息的ID
            self._pending_replies[f"{owner_id}:{info_msg.message_id}"] = {
                "user_id": user_id,
                "user_name": user_name,
                "username": username,
            }

        except Exception as e:
            logger.error(f"转发消息给Bot主人失败: {e}", exc_info=True)
            return PluginResult(
                stop=True,
                reply_text="⚠️ 消息转发失败，请联系管理员。",
                handled=True,
            )

        # 转发后不阻断AI回复，让AI也正常回复用户
        return PluginResult()

    async def _handle_owner_reply(
        self,
        bot: Bot,
        message: Message,
        owner_id: int,
    ) -> PluginResult:
        """处理Bot主人的回复（回复转发消息 = 回复用户）"""
        # 检查是否是回复消息
        if not message.reply_to_message:
            return PluginResult()

        reply_to_id = message.reply_to_message.message_id
        cache_key = f"{owner_id}:{reply_to_id}"

        # 查找对应的用户
        user_info = self._pending_replies.get(cache_key)
        if not user_info:
            return PluginResult()

        target_user_id = user_info["user_id"]
        user_name = user_info["user_name"]
        username = user_info["username"]

        try:
            # 复制消息发送给用户（支持各种类型：文本、图片、视频、贴纸等）
            await bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=owner_id,
                message_id=message.message_id,
            )

            # 通知主人发送成功
            safe_name = user_name.replace("_", "\\_")
            await bot.send_message(
                chat_id=owner_id,
                text=f"✅ 已发送给 {safe_name} (@{username})",
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:
            logger.error(f"回复用户失败: {e}", exc_info=True)
            try:
                await bot.send_message(
                    chat_id=owner_id,
                    text=f"❌ 发送失败: {str(e)[:100]}",
                )
            except:
                pass

        return PluginResult(stop=True, handled=True)