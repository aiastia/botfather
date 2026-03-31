"""
Bot 管理器
管理所有子Bot的生命周期：创建、启动、停止、删除
每个子Bot有独立的插件链和消息处理器
支持 Polling 和 Webhook 两种运行模式
"""
import logging
from typing import Dict, Optional

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, Message
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config.settings import settings
from database.base import DatabaseBase
from database.models import Bot as BotRecord, BotConfig
from plugins.base import PluginChain, PluginContext
from plugins.auth import AuthPlugin
from plugins.command import CommandPlugin
from plugins.ai import AIPlugin
from plugins.reply import ReplyPlugin
from plugins.forward import ForwardPlugin

logger = logging.getLogger(__name__)


class ManagedBot:
    """被管理的子Bot实例"""

    def __init__(self, bot: Bot, dispatcher: Dispatcher, plugin_chain: PluginChain):
        self.bot = bot
        self.dispatcher = dispatcher
        self.plugin_chain = plugin_chain


class BotManager:
    """
    Bot管理器核心类

    负责：
    - 注册 / 注销子Bot
    - 为每个子Bot创建独立的 Dispatcher 和插件链
    - 管理子Bot的运行状态
    """

    def __init__(self, db: DatabaseBase):
        self.db = db
        self._bots: Dict[int, ManagedBot] = {}

    @staticmethod
    async def _register_sub_bot_commands(bot: Bot):
        """向 Telegram 注册子Bot的命令菜单（聊天框中显示的命令提示）"""
        commands = [
            BotCommand(command="start", description="查看欢迎信息"),
            BotCommand(command="help", description="查看帮助"),
            BotCommand(command="clear", description="清空对话记忆"),
            BotCommand(command="config", description="查看当前配置"),
        ]
        await bot.set_my_commands(commands)

    def _create_plugin_chain(self) -> PluginChain:
        """创建默认插件链"""
        chain = PluginChain()
        chain.register(AuthPlugin())       # 5  - 权限校验
        chain.register(CommandPlugin())     # 10 - 命令处理
        chain.register(ForwardPlugin())     # 30 - 消息转发给Bot主人
        chain.register(AIPlugin())          # 50 - AI对话
        reply_plugin = ReplyPlugin()        # 99 - 统一回复
        reply_plugin.db = self.db
        chain.register(reply_plugin)
        return chain

    async def register_bot(self, bot_record: BotRecord) -> bool:
        """注册一个子Bot到管理器"""
        if bot_record.id in self._bots:
            logger.info(f"Bot @{bot_record.bot_username} 已注册，跳过")
            return True

        try:
            bot = Bot(
                token=bot_record.bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
            )
            dp = Dispatcher()
            plugin_chain = self._create_plugin_chain()
            bot_config = await self.db.get_bot_config(bot_record.id)
            managed = ManagedBot(bot, dp, plugin_chain)

            async def message_handler(
                message: Message,
                _br=bot_record,
                _bc=bot_config,
                _pc=plugin_chain,
                _mg=managed,
            ):
                await self._handle_message(message, _br, _bc, _pc, _mg)

            dp.message.register(message_handler)

            # 注册子Bot命令菜单到 Telegram（非致命，失败不影响Bot运行）
            try:
                await self._register_sub_bot_commands(bot)
            except Exception as cmd_err:
                logger.warning(f"Bot @{bot_record.bot_username} 命令菜单注册失败: {cmd_err}")

            self._bots[bot_record.id] = managed
            logger.info(f"Bot @{bot_record.bot_username} 注册成功（命令菜单已注册）")
            return True

        except Exception as e:
            logger.error(f"注册 Bot 失败: {e}", exc_info=True)
            return False

    async def unregister_bot(self, bot_id: int) -> bool:
        """注销一个子Bot"""
        managed = self._bots.pop(bot_id, None)
        if managed:
            await managed.plugin_chain.stop_all()
            session = managed.bot.session
            if session and not session.closed:
                await session.close()
            logger.info(f"Bot ID={bot_id} 已注销")
            return True
        return False

    async def stop_bot(self, bot_id: int) -> bool:
        """停止子Bot"""
        managed = self._bots.get(bot_id)
        if not managed:
            return False
        try:
            await managed.plugin_chain.stop_all()
            await self.db.update_bot_status(bot_id, "stopped")
            logger.info(f"Bot ID={bot_id} 已停止")
            return True
        except Exception as e:
            logger.error(f"停止 Bot ID={bot_id} 失败: {e}", exc_info=True)
            return False

    async def _handle_message(
        self,
        message: Message,
        bot_record: BotRecord,
        bot_config: Optional[BotConfig],
        plugin_chain: PluginChain,
        managed: ManagedBot,
    ):
        """子Bot消息处理核心"""
        try:
            ctx = PluginContext(
                bot_record=bot_record,
                bot_config=bot_config,
                user_id=message.from_user.id if message.from_user else 0,
            )

            # 加载对话历史
            if bot_config and bot_config.ai_enabled and self.db:
                conversations = await self.db.get_conversations(
                    bot_record.id, ctx.user_id, limit=20
                )
                history = [
                    {"role": c.role, "content": c.content} for c in conversations
                ]
                ctx.set("conversation_history", history)

            # 执行插件链
            result = await plugin_chain.execute(managed.bot, message, ctx)

            # 将回复文本传递给 ReplyPlugin
            if result.reply_text:
                ctx.set("pending_reply", result.reply_text)
                for plugin in plugin_chain.get_plugins():
                    if plugin.name == "reply":
                        await plugin.on_message(managed.bot, message, ctx)
                        break

        except Exception as e:
            logger.error(
                f"处理消息失败 (Bot=@{bot_record.bot_username}): {e}",
                exc_info=True,
            )

    async def load_all_bots(self):
        """从数据库加载所有活跃的Bot"""
        active_bots = await self.db.get_all_active_bots()
        logger.info(f"从数据库加载 {len(active_bots)} 个活跃Bot")
        for bot_record in active_bots:
            success = await self.register_bot(bot_record)
            if success:
                logger.info(f"  OK @{bot_record.bot_username} 已加载")
            else:
                logger.error(f"  FAIL @{bot_record.bot_username} 加载失败")

    async def setup_webhook_for_bot(self, bot_id: int) -> bool:
        """为指定子Bot设置 webhook（动态添加时使用）"""
        managed = self._bots.get(bot_id)
        if not managed:
            logger.error(f"设置 webhook 失败: Bot ID={bot_id} 未注册")
            return False

        if settings.BOT_MODE != "webhook":
            return True  # polling 模式无需设置

        try:
            sub_url = settings.sub_webhook_url_template.format(bot_id=bot_id)
            secret = settings.WEBHOOK_SECRET or None
            await managed.bot.set_webhook(
                url=sub_url,
                secret_token=secret,
                drop_pending_updates=True,
                allowed_updates=["message"],
            )
            logger.info(f"子Bot {bot_id} webhook 已设置: {sub_url}")
            return True
        except Exception as e:
            logger.error(f"子Bot {bot_id} 设置 webhook 失败: {e}", exc_info=True)
            return False

    async def remove_webhook_for_bot(self, bot_id: int) -> bool:
        """移除指定子Bot的 webhook"""
        managed = self._bots.get(bot_id)
        if not managed:
            return False

        if settings.BOT_MODE != "webhook":
            return True

        try:
            await managed.bot.delete_webhook(drop_pending_updates=True)
            logger.info(f"子Bot {bot_id} webhook 已移除")
            return True
        except Exception as e:
            logger.error(f"子Bot {bot_id} 移除 webhook 失败: {e}", exc_info=True)
            return False

    def get_all_dispatchers(self) -> Dict[int, Dispatcher]:
        """获取所有Bot的Dispatcher"""
        return {bid: m.dispatcher for bid, m in self._bots.items()}

    def get_all_bots(self) -> Dict[int, ManagedBot]:
        """获取所有被管理的Bot"""
        return self._bots

    @property
    def active_count(self) -> int:
        """当前活跃Bot数量"""
        return len(self._bots)
