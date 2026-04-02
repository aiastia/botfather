"""
Bot 管理命令处理器
处理 Bot 的添加、查看、删除、启动、停止等操作
"""
import logging
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database.models import Bot as BotRecord, BotConfig
from config.settings import settings

logger = logging.getLogger(__name__)

router = Router()


# ==================== FSM 状态定义 ====================
class AddBotStates(StatesGroup):
    waiting_for_token = State()


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


# ==================== /add_bot 命令 ====================
@router.message(Command("add_bot", "addbot"))
async def cmd_add_bot(message: Message, state: FSMContext):
    """添加 Bot - 第一步：请求Token"""
    await message.answer(
        "🔑 请发送你的 Bot Token：\n\n"
        "（从 @BotFather 获取，格式如 <code>123456:ABC-DEF...</code>）\n\n"
        "发送 /cancel 取消操作。",
    )
    await state.set_state(AddBotStates.waiting_for_token)


@router.message(AddBotStates.waiting_for_token, Command("cancel"))
async def cmd_add_bot_cancel(message: Message, state: FSMContext):
    """取消添加"""
    await state.clear()
    await message.answer("❌ 已取消添加 Bot。")


@router.message(AddBotStates.waiting_for_token)
async def process_add_bot_token(message: Message, state: FSMContext):
    """处理用户输入的Token"""
    token = message.text.strip() if message.text else ""

    # 基本格式校验
    if not token or ":" not in token:
        await message.answer("❌ Token 格式不正确，请重新发送或 /cancel 取消。")
        return

    owner_id = message.from_user.id
    mgr = get_bot_manager()

    # 校验Token（调用Telegram API）
    await message.answer("⏳ 正在校验 Token...")

    test_bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        bot_info = await test_bot.get_me()
    except Exception as e:
        await message.answer(f"❌ Token 校验失败：{str(e)[:100]}\n\n请检查Token是否正确。")
        return
    finally:
        # 确保临时 Bot 的 session 被关闭
        if not test_bot.session.closed:
            await test_bot.session.close()

    # 检查是否已添加
    existing = await mgr.db.get_bot_by_token(token)
    if existing and existing.status != "deleted":
        await message.answer(
            f"⚠️ Bot @{bot_info.username} 已经被添加过了。\n"
            f"如需重新添加，请先 /delete_bot 删除。"
        )
        await state.clear()
        return

    # 保存到数据库
    record = BotRecord(
        owner_id=owner_id,
        bot_token=token,
        bot_id=bot_info.id,
        bot_username=bot_info.username or "",
        bot_firstname=bot_info.first_name,
        status="active",
    )
    record_id = await mgr.db.add_bot(record)
    record.id = record_id

    # 创建默认配置
    config = BotConfig(
        bot_id=record_id,
        ai_enabled=True,
        ai_model=settings.AI_MODEL,
        ai_temperature=settings.AI_TEMPERATURE,
        ai_max_tokens=settings.AI_MAX_TOKENS,
    )
    await mgr.db.create_bot_config(config)

    # 注册到BotManager
    await mgr.register_bot(record)

    # Webhook 模式下自动设置 webhook
    if settings.BOT_MODE == "webhook":
        await mgr.setup_webhook_for_bot(record.id)

    await message.answer(
        f"✅ Bot 添加成功！\n\n"
        f"🤖 名称：{bot_info.first_name}\n"
        f"📌 用户名：@{bot_info.username}\n"
        f"🆔 Bot ID：<code>{bot_info.id}</code>\n\n"
        f"现在你可以直接向 @{bot_info.username} 发送消息来使用 AI 助手了！",
    )
    await state.clear()
    logger.info(f"用户 {owner_id} 添加了 Bot @{bot_info.username}")


# ==================== /my_bots 命令 ====================
@router.message(Command("my_bots", "mybots"))
async def cmd_my_bots(message: Message):
    """查看用户的所有Bot"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    bots = await mgr.db.get_bots_by_owner(owner_id)

    if not bots:
        await message.answer("📭 你还没有添加任何 Bot。\n\n使用 /add_bot 开始添加！")
        return

    text = "📋 <b>我的 Bot 列表：</b>\n\n"
    for i, bot in enumerate(bots, 1):
        status_emoji = "🟢" if bot.status == "active" else "🔴"
        text += (
            f"{i}. {status_emoji} <b>{bot.bot_firstname}</b>\n"
            f"   @{bot.bot_username} | ID: <code>{bot.id}</code>\n\n"
        )

    text += f"共 {len(bots)} 个 Bot"
    await message.answer(text)


# ==================== /delete_bot 命令 ====================
@router.message(Command("delete_bot", "deletebot"))
async def cmd_delete_bot(message: Message, state: FSMContext):
    """删除Bot"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    bots = await mgr.db.get_bots_by_owner(owner_id)

    if not bots:
        await message.answer("📭 你没有可删除的 Bot。")
        return

    text = "🗑️ <b>请回复要删除的 Bot 编号：</b>\n\n"
    for i, bot in enumerate(bots, 1):
        text += f"{i}. @{bot.bot_username} ({bot.bot_firstname})\n"

    text += "\n发送 /cancel 取消"
    await message.answer(text)

    # 存储bot列表到状态
    await state.set_data({"delete_bots": [b.to_dict() for b in bots]})


# ==================== /start_bot 命令 ====================
@router.message(Command("start_bot", "startbot"))
async def cmd_start_bot(message: Message):
    """启动Bot（提示使用说明）"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    bots = await mgr.db.get_bots_by_owner(owner_id)

    if not bots:
        await message.answer("📭 你没有 Bot。使用 /add_bot 添加。")
        return

    text = "🚀 <b>Bot 启动状态：</b>\n\n"
    for bot in bots:
        managed = mgr.get_all_bots().get(bot.id)
        status = "🟢 运行中" if managed else "🔴 未运行"
        text += f"- @{bot.bot_username}: {status}\n"

    text += "\n💡 添加的 Bot 会自动启动，如需重启请先 /stop_bot 再重新添加。"
    await message.answer(text)


# ==================== /stop_bot 命令 ====================
@router.message(Command("stop_bot", "stopbot"))
async def cmd_stop_bot(message: Message):
    """停止Bot"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    bots = await mgr.db.get_bots_by_owner(owner_id)
    stopped = 0

    for bot in bots:
        if await mgr.stop_bot(bot.id):
            stopped += 1

    await message.answer(f"⏹️ 已停止 {stopped} 个 Bot。")