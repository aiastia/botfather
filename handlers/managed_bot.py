"""
Managed Bots 处理器（Bot API 9.6）
支持一键创建托管 Bot、获取/重置 Token、自动处理 Managed Bot 更新事件
"""
import logging
from aiogram import Router, Bot, F
from aiogram.types import Message, Update
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config.settings import settings

logger = logging.getLogger(__name__)

router = Router()


class CreateBotStates(StatesGroup):
    """Managed Bot 创建流程"""
    waiting_for_name = State()
    waiting_for_username = State()


def get_bot_manager():
    """获取 BotManager 实例"""
    import sys
    main_module = sys.modules.get("__main__")
    if main_module and hasattr(main_module, "bot_manager"):
        mgr = main_module.bot_manager
        if mgr is not None:
            return mgr
    logger.error("bot_manager 未初始化")
    return None


# ==================== /create_bot 一键创建托管 Bot ====================
@router.message(Command("create_bot", "createbot"))
async def cmd_create_bot(message: Message, state: FSMContext):
    """创建托管 Bot - 第一步：输入Bot名称"""
    await message.answer(
        "🤖 <b>创建托管 Bot</b>\n\n"
        "请输入 Bot 的 <b>显示名称</b>（如：我的AI助手）：\n\n"
        "发送 /cancel 取消操作。",
    )
    await state.set_state(CreateBotStates.waiting_for_name)


@router.message(CreateBotStates.waiting_for_name, Command("cancel"))
async def cmd_create_bot_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ 已取消创建 Bot。")


@router.message(CreateBotStates.waiting_for_name)
async def process_create_bot_name(message: Message, state: FSMContext):
    """处理Bot名称输入"""
    name = message.text.strip() if message.text else ""
    if not name or len(name) > 64:
        await message.answer("❌ 名称不能为空且不能超过64个字符，请重新输入：")
        return

    await state.update_data(bot_name=name)
    await message.answer(
        f"✅ 名称：<b>{name}</b>\n\n"
        "请输入 Bot 的 <b>用户名</b>（必须以 <code>bot</code> 结尾，如：<code>my_ai_bot</code>）：\n\n"
        "发送 /cancel 取消操作。",
    )
    await state.set_state(CreateBotStates.waiting_for_username)


@router.message(CreateBotStates.waiting_for_username, Command("cancel"))
async def cmd_create_bot_cancel2(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ 已取消创建 Bot。")


@router.message(CreateBotStates.waiting_for_username)
async def process_create_bot_username(message: Message, state: FSMContext):
    """处理Bot用户名输入，生成深度链接"""
    username = message.text.strip().lstrip("@") if message.text else ""

    if not username or not username.endswith("bot"):
        await message.answer(
            "❌ 用户名必须以 <code>bot</code> 结尾。\n"
            "例如：<code>my_ai_bot</code>\n\n请重新输入："
        )
        return

    data = await state.get_data()
    bot_name = data.get("bot_name", "My Bot")
    await state.clear()

    mgr = get_bot_manager()
    if not mgr:
        await message.answer("❌ 系统错误，请联系管理员。")
        return

    master_bot_username = settings.MASTER_BOT_USERNAME
    if not master_bot_username:
        await message.answer(
            "❌ 未配置 MASTER_BOT_USERNAME，无法创建托管 Bot。\n"
            "请联系管理员在 .env 中配置。",
        )
        return

    # 生成深度链接让用户通过 Telegram 创建 Managed Bot
    create_link = (
        f"https://t.me/newbot/{master_bot_username}/{username}?name={bot_name}"
    )

    await message.answer(
        f"🤖 <b>创建托管 Bot</b>\n\n"
        f"📌 名称：{bot_name}\n"
        f"👤 用户名：@{username}\n\n"
        f"👇 <b>点击下方链接创建 Bot：</b>\n"
        f'<a href="{create_link}">点击创建 @{username}</a>\n\n'
        f"创建完成后，Bot 会自动注册到本平台。",
        disable_web_page_preview=True,
    )
    logger.info(f"用户 {message.from_user.id} 请求创建托管 Bot @{username}")


# ==================== /token_bot 获取托管 Bot Token ====================
@router.message(Command("token_bot", "tokenbot"))
async def cmd_token_bot(message: Message, state: FSMContext):
    """获取托管 Bot 的 Token"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    bots = await mgr.db.get_bots_by_owner(owner_id)

    if not bots:
        await message.answer("📭 你没有 Bot。使用 /add_bot 或 /create_bot 添加。")
        return

    text = "🔑 <b>请回复要获取 Token 的 Bot 编号：</b>\n\n"
    for i, bot in enumerate(bots, 1):
        text += f"{i}. @{bot.bot_username} ({bot.bot_firstname})\n"
    text += "\n发送 /cancel 取消"
    await message.answer(text)
    await state.set_data({"token_bots": [b.to_dict() for b in bots]})
    await state.set_state("waiting_for_token_bot_index")


@router.message(State("waiting_for_token_bot_index"), Command("cancel"))
async def cmd_token_bot_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ 已取消。")


@router.message(State("waiting_for_token_bot_index"))
async def process_token_bot(message: Message, state: FSMContext):
    """处理获取 Token 选择"""
    data = await state.get_data()
    bots_data = data.get("token_bots", [])
    await state.clear()

    try:
        idx = int(message.text.strip()) - 1
        if idx < 0 or idx >= len(bots_data):
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("❌ 请输入有效的编号。")
        return

    bot_data = bots_data[idx]

    try:
        master_bot = Bot(
            token=settings.MASTER_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        from aiogram.methods.get_managed_bot_token import GetManagedBotToken

        result = await master_bot(
            GetManagedBotToken(managed_bot_id=bot_data["bot_id"])
        )
        await message.answer(
            f"🔑 <b>Bot Token</b> - @{bot_data['bot_username']}:\n\n"
            f"<code>{result.token}</code>\n\n"
            f"⚠️ 请妥善保管 Token，不要泄露给他人！",
        )
    except Exception as e:
        logger.error(f"获取 Managed Bot Token 失败: {e}", exc_info=True)
        await message.answer(
            f"❌ 获取 Token 失败：{str(e)[:200]}\n\n"
            "可能该 Bot 不是托管 Bot，或主 Bot 没有 Managed Bot 权限。",
        )


# ==================== /reset_token 重置托管 Bot Token ====================
@router.message(Command("reset_token", "resettoken"))
async def cmd_reset_token(message: Message, state: FSMContext):
    """重置托管 Bot 的 Token"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    bots = await mgr.db.get_bots_by_owner(owner_id)

    if not bots:
        await message.answer("📭 你没有 Bot。")
        return

    text = "🔄 <b>请回复要重置 Token 的 Bot 编号：</b>\n\n"
    for i, bot in enumerate(bots, 1):
        text += f"{i}. @{bot.bot_username} ({bot.bot_firstname})\n"
    text += "\n⚠️ 重置后旧 Token 将立即失效！\n发送 /cancel 取消"
    await message.answer(text)
    await state.set_data({"reset_bots": [b.to_dict() for b in bots]})
    await state.set_state("waiting_for_reset_token_index")


@router.message(State("waiting_for_reset_token_index"), Command("cancel"))
async def cmd_reset_token_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ 已取消。")


@router.message(State("waiting_for_reset_token_index"))
async def process_reset_token(message: Message, state: FSMContext):
    """处理重置 Token"""
    data = await state.get_data()
    bots_data = data.get("reset_bots", [])
    await state.clear()

    try:
        idx = int(message.text.strip()) - 1
        if idx < 0 or idx >= len(bots_data):
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("❌ 请输入有效的编号。")
        return

    bot_data = bots_data[idx]
    mgr = get_bot_manager()

    try:
        master_bot = Bot(
            token=settings.MASTER_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        from aiogram.methods.replace_managed_bot_token import ReplaceManagedBotToken

        result = await master_bot(
            ReplaceManagedBotToken(managed_bot_id=bot_data["bot_id"])
        )

        # 更新数据库 Token 并重新注册 Bot
        await mgr.db.update_bot_token(bot_data["id"], result.token)
        await mgr.unregister_bot(bot_data["id"])
        updated_record = await mgr.db.get_bot(bot_data["id"])
        if updated_record:
            updated_record.bot_token = result.token
            await mgr.register_bot(updated_record)

        await message.answer(
            f"✅ <b>Token 已重置</b> - @{bot_data['bot_username']}:\n\n"
            f"<code>{result.token}</code>\n\n"
            f"⚠️ 旧 Token 已失效，Bot 已自动重新注册。",
        )
    except Exception as e:
        logger.error(f"重置 Managed Bot Token 失败: {e}", exc_info=True)
        await message.answer(
            f"❌ 重置 Token 失败：{str(e)[:200]}\n\n"
            "可能该 Bot 不是托管 Bot，或主 Bot 没有 Managed Bot 权限。",
        )


# ==================== 处理 Managed Bot 更新事件 ====================
@router.update(F.managed_bot)
async def handle_managed_bot_update(update: Update):
    """
    处理托管 Bot 的更新事件
    当托管 Bot 被创建或 Token 变更时自动触发
    """
    mgr = get_bot_manager()
    if not mgr or not update.managed_bot:
        return

    managed_bot_data = update.managed_bot
    logger.info(f"收到 Managed Bot 更新: {managed_bot_data}")

    try:
        from aiogram.types.managed_bot_updated import ManagedBotUpdated

        if isinstance(managed_bot_data, ManagedBotUpdated):
            bot_id = managed_bot_data.bot.id
            new_token = getattr(managed_bot_data, "token", None)

            if new_token:
                await mgr.db.update_bot_token(bot_id, new_token)
                await mgr.unregister_bot(bot_id)
                record = await mgr.db.get_bot(bot_id)
                if record:
                    record.bot_token = new_token
                    await mgr.register_bot(record)
                logger.info(f"Managed Bot {bot_id} Token 已自动更新")
    except Exception as e:
        logger.error(f"处理 Managed Bot 更新失败: {e}", exc_info=True)