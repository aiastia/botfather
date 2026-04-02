"""
管理员命令处理器
处理管理员相关的所有命令
"""
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from config.settings import settings

logger = logging.getLogger(__name__)

router = Router()


# ==================== 辅助函数 ====================
def get_bot_manager():
    """获取 BotManager 实例（从 main.py 注入）"""
    import sys
    main_module = sys.modules.get('__main__')
    if main_module and hasattr(main_module, 'bot_manager'):
        mgr = main_module.bot_manager
        if mgr is not None:
            return mgr
    logger.error("bot_manager 未初始化！请确保程序已正确启动。")
    return None


def _is_admin(user_id: int) -> bool:
    """检查是否是管理员"""
    return user_id in settings.admin_id_list


# ==================== /admin 命令 ====================
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """管理员面板"""
    if not _is_admin(message.from_user.id):
        await message.answer("❌ 你不是管理员。")
        return

    mgr = get_bot_manager()
    all_bots = await mgr.db.get_all_active_bots()

    total_bots = len(all_bots)
    total_users = len(set(b.owner_id for b in all_bots))

    text = (
        "🔧 管理员面板\n\n"
        f"📊 统计：{total_bots} 个Bot / {total_users} 个用户\n\n"
        "命令：\n"
        "/admin_bots - 查看所有Bot列表\n"
        "/admin_toggle_ai <bot_id> - 开关Bot的AI\n"
        "/admin_set_key <bot_id> <key> - 为Bot设置API Key\n"
    )
    await message.answer(text)


# ==================== /admin_bots 命令 ====================
@router.message(Command("admin_bots"))
async def cmd_admin_bots(message: Message):
    """管理员：查看所有Bot"""
    if not _is_admin(message.from_user.id):
        return

    mgr = get_bot_manager()
    all_bots = await mgr.db.get_all_active_bots()

    if not all_bots:
        await message.answer("📭 没有任何Bot。")
        return

    text = "📋 所有 Bot 列表：\n\n"
    for bot in all_bots:
        bot_config = await mgr.db.get_bot_config(bot.id)
        ai_status = "✅" if (bot_config and bot_config.ai_enabled) else "❌"
        custom_key = "🔑" if (bot_config and bot_config.ai_api_key) else "🌐"
        text += (
            f"ID:{bot.id} | {ai_status}AI | {custom_key} | "
            f"@{bot.bot_username} (Owner: {bot.owner_id})\n"
        )

    await message.answer(text)


# ==================== /admin_toggle_ai 命令 ====================
@router.message(Command("admin_toggle_ai"))
async def cmd_admin_toggle_ai(message: Message):
    """管理员：开关Bot的AI"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("用法：/admin_toggle_ai <bot_id>")
        return

    try:
        bot_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ Bot ID 必须是数字。")
        return

    mgr = get_bot_manager()
    bot_config = await mgr.db.get_bot_config(bot_id)
    if not bot_config:
        await message.answer(f"❌ Bot ID {bot_id} 没有配置。")
        return

    bot_config.ai_enabled = not bot_config.ai_enabled
    await mgr.db.update_bot_config(bot_config)
    status = "✅ 开启" if bot_config.ai_enabled else "❌ 关闭"
    await message.answer(f"Bot ID {bot_id} 的 AI 已{status}")