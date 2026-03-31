"""
主Bot命令处理器
处理用户与主控Bot的交互：添加Bot、查看Bot列表、删除Bot等
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database.base import DatabaseBase
from database.models import Bot as BotRecord, BotConfig
from config.settings import settings

logger = logging.getLogger(__name__)

router = Router()


# ==================== 启动时注册命令菜单 ====================
from aiogram.types import BotCommand

async def register_bot_commands(bot: Bot):
    """向 Telegram 注册 Bot 命令菜单（聊天框中显示的命令提示）"""
    commands = [
        BotCommand(command="add_bot", description="添加新 Bot"),
        BotCommand(command="my_bots", description="查看我的 Bot"),
        BotCommand(command="delete_bot", description="删除 Bot"),
        BotCommand(command="start_bot", description="查看 Bot 启动状态"),
        BotCommand(command="stop_bot", description="停止 Bot"),
        BotCommand(command="config", description="查看/配置 Bot 参数"),
        BotCommand(command="help", description="查看帮助"),
    ]
    await bot.set_my_commands(commands)
    logger.info("已注册 Bot 命令菜单")


# ==================== FSM 状态定义 ====================
class AddBotStates(StatesGroup):
    waiting_for_token = State()


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


# ==================== /start 命令 ====================
@router.message(Command("start"))
async def cmd_start(message: Message):
    """初始化 / 欢迎信息"""
    text = (
        "👋 **欢迎使用 TG Bot 托管平台！**\n\n"
        "我可以帮你管理多个 Telegram Bot，"
        "让每个 Bot 都变成你的 **AI 私聊助手**。\n\n"
        "📌 **快速开始：**\n"
        "/add_bot - 添加一个新 Bot\n"
        "/my_bots - 查看我的 Bot 列表\n"
        "/help - 查看完整帮助\n"
    )
    await message.answer(text)


# ==================== /help 命令 ====================
@router.message(Command("help"))
async def cmd_help(message: Message):
    """帮助信息"""
    text = (
        "📖 **使用帮助**\n\n"
        "**Bot 管理：**\n"
        "/add_bot - 添加新 Bot\n"
        "/my_bots - 查看我的 Bot\n"
        "/delete_bot - 删除 Bot\n\n"
        "**Bot 配置：**\n"
        "/config - 配置 Bot 参数\n"
        "/start_bot - 启动 Bot\n"
        "/stop_bot - 停止 Bot\n\n"
        "**💡 提示：**\n"
        "1. 先在 @BotFather 创建一个 Bot\n"
        "2. 使用 /add_bot 将其添加到平台\n"
        "3. 向你的 Bot 发消息即可开始对话\n"
    )
    await message.answer(text)


# ==================== /add_bot 命令 ====================
@router.message(Command("add_bot", "addbot"))
async def cmd_add_bot(message: Message, state: FSMContext):
    """添加 Bot - 第一步：请求Token"""
    await message.answer(
        "🔑 请发送你的 Bot Token：\n\n"
        "（从 @BotFather 获取，格式如 `123456:ABC-DEF...`）\n\n"
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

    try:
        test_bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        )
        bot_info = await test_bot.get_me()
    except Exception as e:
        await message.answer(f"❌ Token 校验失败：{str(e)[:100]}\n\n请检查Token是否正确。")
        return

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
        f"🆔 Bot ID：`{bot_info.id}`\n\n"
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

    text = "📋 **我的 Bot 列表：**\n\n"
    for i, bot in enumerate(bots, 1):
        status_emoji = "🟢" if bot.status == "active" else "🔴"
        text += (
            f"{i}. {status_emoji} **{bot.bot_firstname}**\n"
            f"   @{bot.bot_username} | ID: `{bot.id}`\n\n"
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

    text = "🗑️ **请回复要删除的 Bot 编号：**\n\n"
    for i, bot in enumerate(bots, 1):
        text += f"{i}. @{bot.bot_username} ({bot.bot_firstname})\n"

    text += "\n发送 /cancel 取消"
    await message.answer(text)

    # 存储bot列表到状态
    await state.set_data({"delete_bots": [b.to_dict() for b in bots]})


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """通用取消"""
    await state.clear()
    await message.answer("❌ 操作已取消。")


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

    text = "🚀 **Bot 启动状态：**\n\n"
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


# ==================== /config 命令 ====================
@router.message(Command("config"))
async def cmd_config(message: Message):
    """查看Bot配置"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    bots = await mgr.db.get_bots_by_owner(owner_id)

    if not bots:
        await message.answer("📭 你没有 Bot。使用 /add_bot 添加。")
        return

    text = "⚙️ **Bot 配置信息：**\n\n"
    for bot in bots:
        bot_config = await mgr.db.get_bot_config(bot.id)
        if bot_config:
            text += (
                f"🤖 **@{bot.bot_username}**\n"
                f"   AI: {'✅ 开启' if bot_config.ai_enabled else '❌ 关闭'}\n"
                f"   模型: `{bot_config.ai_model}`\n"
                f"   温度: `{bot_config.ai_temperature}`\n"
                f"   最大Token: `{bot_config.ai_max_tokens}`\n"
                f"   自定义API: {'✅' if bot_config.ai_api_base_url else '❌ 使用全局配置'}\n\n"
            )
        else:
            text += f"🤖 @{bot.bot_username}: 暂无配置（使用全局默认）\n\n"

    text += (
        "💡 全局 AI 配置（.env）：\n"
        f"   模型: `{settings.AI_MODEL}`\n"
        f"   API: `{settings.AI_API_BASE_URL}`\n"
    )
    await message.answer(text)
