"""
Bot AI 配置命令处理器
处理 /config、/setkey、/setapi、/setmodel 等配置操作
"""
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

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


def _clear_ai_client_cache():
    """清除 AI 客户端缓存，使新配置生效"""
    try:
        from plugins.ai import AIPlugin
        AIPlugin._clients.clear()
    except Exception:
        pass


# ==================== FSM 状态定义 ====================
class ConfigStates(StatesGroup):
    """AI 配置状态"""
    waiting_for_bot_select = State()
    waiting_for_api_key = State()
    waiting_for_api_url = State()
    waiting_for_model = State()


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

    text = "⚙️ <b>Bot 配置信息：</b>\n\n"
    for bot in bots:
        bot_config = await mgr.db.get_bot_config(bot.id)
        if bot_config:
            text += (
                f"🤖 <b>@{bot.bot_username}</b>\n"
                f"   AI: {'✅ 开启' if bot_config.ai_enabled else '❌ 关闭'}\n"
                f"   模型: <code>{bot_config.ai_model}</code>\n"
                f"   温度: <code>{bot_config.ai_temperature}</code>\n"
                f"   最大Token: <code>{bot_config.ai_max_tokens}</code>\n"
                f"   自定义API: {'✅' if bot_config.ai_api_base_url else '❌ 使用全局配置'}\n\n"
            )
        else:
            text += f"🤖 @{bot.bot_username}: 暂无配置（使用全局默认）\n\n"

    text += (
        "💡 全局 AI 配置（.env）：\n"
        f"   模型: <code>{settings.AI_MODEL}</code>\n"
        f"   API: <code>{settings.AI_API_BASE_URL}</code>\n"
    )
    await message.answer(text)


# ==================== /setkey 命令 ====================
@router.message(Command("setkey"))
async def cmd_setkey(message: Message, state: FSMContext):
    """设置自己Bot的 AI API Key"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    bots = await mgr.db.get_bots_by_owner(owner_id)

    if not bots:
        await message.answer("📭 你没有 Bot。使用 /add_bot 添加。")
        return

    if len(bots) == 1:
        # 只有一个Bot，直接跳到输入Key
        await state.set_data({"config_bot_id": bots[0].id})
        await message.answer(
            f"🔑 请发送你的 OpenAI API Key：\n\n"
            f"（将被设置给 @{bots[0].bot_username}）\n\n"
            f"发送 /cancel 取消"
        )
        await state.set_state(ConfigStates.waiting_for_api_key)
    else:
        text = "🤖 请选择要配置的 Bot 编号：\n\n"
        for i, bot in enumerate(bots, 1):
            text += f"{i}. @{bot.bot_username}\n"
        text += "\n发送 /cancel 取消"
        await message.answer(text)
        await state.set_data({
            "config_bot_list": [b.id for b in bots],
        })
        await state.set_state(ConfigStates.waiting_for_bot_select)
        # 标记下一步是 setkey
        await state.update_data(next_action="setkey")


# ==================== /setapi 命令 ====================
@router.message(Command("setapi"))
async def cmd_setapi(message: Message, state: FSMContext):
    """设置自己Bot的 AI API Base URL"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    bots = await mgr.db.get_bots_by_owner(owner_id)

    if not bots:
        await message.answer("📭 你没有 Bot。使用 /add_bot 添加。")
        return

    if len(bots) == 1:
        await state.set_data({"config_bot_id": bots[0].id})
        await message.answer(
            "🌐 请发送 API Base URL：\n\n"
            f"例如：<code>https://api.openai.com/v1</code>\n"
            f"或中转地址：<code>https://your-proxy.com/v1</code>\n\n"
            f"发送 /cancel 取消"
        )
        await state.set_state(ConfigStates.waiting_for_api_url)
    else:
        text = "🤖 请选择要配置的 Bot 编号：\n\n"
        for i, bot in enumerate(bots, 1):
            text += f"{i}. @{bot.bot_username}\n"
        text += "\n发送 /cancel 取消"
        await message.answer(text)
        await state.set_data({
            "config_bot_list": [b.id for b in bots],
            "next_action": "setapi",
        })
        await state.set_state(ConfigStates.waiting_for_bot_select)


# ==================== /setmodel 命令 ====================
@router.message(Command("setmodel"))
async def cmd_setmodel(message: Message, state: FSMContext):
    """设置自己Bot的 AI 模型"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    bots = await mgr.db.get_bots_by_owner(owner_id)

    if not bots:
        await message.answer("📭 你没有 Bot。使用 /add_bot 添加。")
        return

    if len(bots) == 1:
        await state.set_data({"config_bot_id": bots[0].id})
        await message.answer(
            "🧠 请发送 AI 模型名称：\n\n"
            "例如：<code>gpt-3.5-turbo</code>、<code>gpt-4</code>、<code>gpt-4o</code>\n\n"
            "发送 /cancel 取消"
        )
        await state.set_state(ConfigStates.waiting_for_model)
    else:
        text = "🤖 请选择要配置的 Bot 编号：\n\n"
        for i, bot in enumerate(bots, 1):
            text += f"{i}. @{bot.bot_username}\n"
        text += "\n发送 /cancel 取消"
        await message.answer(text)
        await state.set_data({
            "config_bot_list": [b.id for b in bots],
            "next_action": "setmodel",
        })
        await state.set_state(ConfigStates.waiting_for_bot_select)


# ==================== FSM 状态处理 ====================
@router.message(ConfigStates.waiting_for_bot_select)
async def process_bot_select(message: Message, state: FSMContext):
    """处理Bot选择"""
    data = await state.get_data()
    bot_list = data.get("config_bot_list", [])
    next_action = data.get("next_action", "")

    try:
        idx = int(message.text.strip()) - 1
        if idx < 0 or idx >= len(bot_list):
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("❌ 请输入有效的编号。")
        return

    selected_bot_id = bot_list[idx]
    await state.update_data(config_bot_id=selected_bot_id)

    if next_action == "setkey":
        await message.answer("🔑 请发送你的 OpenAI API Key：\n\n发送 /cancel 取消")
        await state.set_state(ConfigStates.waiting_for_api_key)
    elif next_action == "setapi":
        await message.answer(
            "🌐 请发送 API Base URL：\n\n"
            "例如：<code>https://api.openai.com/v1</code>\n\n"
            "发送 /cancel 取消"
        )
        await state.set_state(ConfigStates.waiting_for_api_url)
    elif next_action == "setmodel":
        await message.answer(
            "🧠 请发送 AI 模型名称：\n\n"
            "例如：<code>gpt-4</code>、<code>gpt-3.5-turbo</code>\n\n"
            "发送 /cancel 取消"
        )
        await state.set_state(ConfigStates.waiting_for_model)


@router.message(ConfigStates.waiting_for_api_key)
async def process_api_key(message: Message, state: FSMContext):
    """保存 API Key"""
    data = await state.get_data()
    bot_id = data.get("config_bot_id")
    if not bot_id:
        await message.answer("❌ 出错了，请重新开始。")
        await state.clear()
        return

    api_key = message.text.strip() if message.text else ""
    if not api_key or len(api_key) < 10:
        await message.answer("❌ API Key 格式不正确，请重新发送。")
        return

    mgr = get_bot_manager()
    bot_config = await mgr.db.get_bot_config(bot_id)
    if bot_config:
        bot_config.ai_api_key = api_key
        await mgr.db.update_bot_config(bot_config)
        # 清除缓存的 OpenAI 客户端
        _clear_ai_client_cache()
        await message.answer("✅ API Key 已更新！")
    else:
        await message.answer("❌ Bot 配置不存在。")

    await state.clear()


@router.message(ConfigStates.waiting_for_api_url)
async def process_api_url(message: Message, state: FSMContext):
    """保存 API URL"""
    data = await state.get_data()
    bot_id = data.get("config_bot_id")
    if not bot_id:
        await message.answer("❌ 出错了，请重新开始。")
        await state.clear()
        return

    url = message.text.strip() if message.text else ""
    if not url.startswith("http"):
        await message.answer("❌ URL 格式不正确，需要以 http 开头。")
        return

    mgr = get_bot_manager()
    bot_config = await mgr.db.get_bot_config(bot_id)
    if bot_config:
        bot_config.ai_api_base_url = url
        await mgr.db.update_bot_config(bot_config)
        _clear_ai_client_cache()
        await message.answer(f"✅ API URL 已更新为：<code>{url}</code>")
    else:
        await message.answer("❌ Bot 配置不存在。")

    await state.clear()


@router.message(ConfigStates.waiting_for_model)
async def process_model(message: Message, state: FSMContext):
    """保存 AI 模型"""
    data = await state.get_data()
    bot_id = data.get("config_bot_id")
    if not bot_id:
        await message.answer("❌ 出错了，请重新开始。")
        await state.clear()
        return

    model = message.text.strip() if message.text else ""
    if not model:
        await message.answer("❌ 模型名称不能为空。")
        return

    mgr = get_bot_manager()
    bot_config = await mgr.db.get_bot_config(bot_id)
    if bot_config:
        bot_config.ai_model = model
        await mgr.db.update_bot_config(bot_config)
        await message.answer(f"✅ AI 模型已更新为：<code>{model}</code>")
    else:
        await message.answer("❌ Bot 配置不存在。")

    await state.clear()