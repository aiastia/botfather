"""
关键词回复管理命令处理器
Bot 主人可以设置关键词自动回复规则
"""
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models import KeywordReply

logger = logging.getLogger(__name__)

router = Router()


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


# ==================== FSM 状态 ====================
class KeywordStates(StatesGroup):
    """关键词管理流程"""
    waiting_for_bot_select = State()
    waiting_for_keyword = State()
    waiting_for_reply = State()
    waiting_for_mode = State()  # 普通/正则
    waiting_for_delete = State()
    waiting_for_toggle = State()


# ==================== /add_keyword 添加关键词 ====================
@router.message(Command("add_keyword", "addkeyword"))
async def cmd_add_keyword(message: Message, state: FSMContext):
    """添加关键词回复 - 选择Bot"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    if not mgr:
        await message.answer("❌ 系统错误。")
        return

    bots = await mgr.db.get_bots_by_owner(owner_id)
    if not bots:
        await message.answer("📭 你没有 Bot。使用 /create_bot 或 /add_bot 添加。")
        return

    if len(bots) == 1:
        await state.set_data({"kw_bot_id": bots[0].id})
        await message.answer(
            f"📝 请输入要匹配的 <b>关键词</b>（发给 @{bots[0].bot_username} 的消息中包含此词即触发）：\n\n"
            f"发送 /cancel 取消",
        )
        await state.set_state(KeywordStates.waiting_for_keyword)
    else:
        text = "🤖 请选择要配置的 Bot 编号：\n\n"
        for i, bot in enumerate(bots, 1):
            text += f"{i}. @{bot.bot_username}\n"
        text += "\n发送 /cancel 取消"
        await message.answer(text)
        await state.set_data({
            "bot_list": [b.id for b in bots],
            "bot_usernames": {b.id: b.bot_username for b in bots},
        })
        await state.set_state(KeywordStates.waiting_for_bot_select)
        await state.update_data(kw_action="add")


@router.message(KeywordStates.waiting_for_bot_select)
async def process_bot_select(message: Message, state: FSMContext):
    """处理Bot选择"""
    data = await state.get_data()
    bot_list = data.get("bot_list", [])

    try:
        idx = int(message.text.strip()) - 1
        if idx < 0 or idx >= len(bot_list):
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("❌ 请输入有效的编号。")
        return

    selected_bot_id = bot_list[idx]
    action = data.get("kw_action", "add")

    await state.update_data(kw_bot_id=selected_bot_id)

    if action == "add":
        bot_usernames = data.get("bot_usernames", {})
        bot_name = bot_usernames.get(selected_bot_id, "")
        await message.answer(
            f"📝 请输入要匹配的 <b>关键词</b>（发给 @{bot_name} 的消息中包含此词即触发）：\n\n"
            f"发送 /cancel 取消",
        )
        await state.set_state(KeywordStates.waiting_for_keyword)


@router.message(KeywordStates.waiting_for_keyword)
async def process_keyword(message: Message, state: FSMContext):
    """处理关键词输入"""
    keyword = message.text.strip() if message.text else ""
    if not keyword or len(keyword) > 200:
        await message.answer("❌ 关键词不能为空且不能超过200个字符，请重新输入：")
        return

    await state.update_data(kw_keyword=keyword)
    await message.answer(
        f"✅ 关键词：<code>{keyword}</code>\n\n"
        f"请输入匹配时要发送的 <b>回复内容</b>：\n\n"
        f"发送 /cancel 取消",
    )
    await state.set_state(KeywordStates.waiting_for_reply)


@router.message(KeywordStates.waiting_for_reply)
async def process_reply(message: Message, state: FSMContext):
    """处理回复内容输入"""
    reply_text = message.text.strip() if message.text else ""
    if not reply_text or len(reply_text) > 4096:
        await message.answer("❌ 回复内容不能为空且不能超过4096个字符，请重新输入：")
        return

    await state.update_data(kw_reply=reply_text)
    await message.answer(
        "🔧 请选择匹配模式：\n\n"
        "1️⃣ 普通匹配 - 消息中包含关键词即触发（不区分大小写）\n"
        "2️⃣ 正则匹配 - 使用正则表达式匹配（高级用户）\n\n"
        "请回复 <b>1</b> 或 <b>2</b>：\n\n"
        "发送 /cancel 取消",
    )
    await state.set_state(KeywordStates.waiting_for_mode)


@router.message(KeywordStates.waiting_for_mode)
async def process_mode(message: Message, state: FSMContext):
    """处理匹配模式选择"""
    text = message.text.strip() if message.text else ""

    if text == "1":
        is_regex = False
    elif text == "2":
        is_regex = True
    else:
        await message.answer("❌ 请回复 <b>1</b>（普通匹配）或 <b>2</b>（正则匹配）：")
        return

    # 如果选择了正则，先验证正则语法
    if is_regex:
        import re
        data = await state.get_data()
        keyword = data.get("kw_keyword", "")
        try:
            re.compile(keyword)
        except re.error as e:
            await message.answer(
                f"❌ 正则语法错误：{e}\n\n"
                f"请重新输入关键词（回复 /cancel 取消）：",
            )
            await state.set_state(KeywordStates.waiting_for_keyword)
            return

    data = await state.get_data()
    bot_id = data.get("kw_bot_id")
    keyword = data.get("kw_keyword", "")
    reply = data.get("kw_reply", "")

    mgr = get_bot_manager()
    if not mgr:
        await message.answer("❌ 系统错误。")
        await state.clear()
        return

    kw = KeywordReply(
        bot_id=bot_id,
        keyword=keyword,
        reply_text=reply,
        is_regex=is_regex,
        enabled=True,
    )
    kw_id = await mgr.db.add_keyword_reply(kw)

    mode_text = "正则匹配" if is_regex else "普通匹配"
    await message.answer(
        f"✅ <b>关键词回复已添加！</b>\n\n"
        f"🆔 规则ID：{kw_id}\n"
        f"🔑 关键词：<code>{keyword}</code>\n"
        f"💬 回复内容：{reply[:100]}{'...' if len(reply) > 100 else ''}\n"
        f"🔧 匹配模式：{mode_text}\n"
        f"📊 状态：✅ 已启用\n\n"
        f"使用 /keywords 查看所有规则\n"
        f"使用 /del_keyword 删除规则\n"
        f"使用 /toggle_keyword 启用/禁用规则",
    )
    await state.clear()


# ==================== /keywords 查看关键词列表 ====================
@router.message(Command("keywords", "keyword_list"))
async def cmd_keywords(message: Message):
    """查看所有关键词回复规则"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    if not mgr:
        await message.answer("❌ 系统错误。")
        return

    bots = await mgr.db.get_bots_by_owner(owner_id)
    if not bots:
        await message.answer("📭 你没有 Bot。")
        return

    has_rules = False
    text = "📝 <b>关键词回复规则列表</b>\n\n"

    for bot in bots:
        rules = await mgr.db.get_keyword_replies(bot.id)
        if rules:
            has_rules = True
            text += f"🤖 <b>@{bot.bot_username}</b>（{len(rules)} 条规则）：\n"
            for rule in rules:
                mode = "regex" if rule.is_regex else "text"
                status = "✅" if rule.enabled else "❌"
                reply_preview = rule.reply_text[:40] + ("..." if len(rule.reply_text) > 40 else "")
                text += (
                    f"  {status} [{rule.id}] <code>{rule.keyword}</code> "
                    f"({mode}) → {reply_preview}\n"
                )
            text += "\n"

    if not has_rules:
        text += "📭 暂无规则。\n\n使用 /add_keyword 添加关键词回复。"

    await message.answer(text)


# ==================== /del_keyword 删除关键词 ====================
@router.message(Command("del_keyword", "delkeyword"))
async def cmd_del_keyword(message: Message, state: FSMContext):
    """删除关键词回复规则"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    if not mgr:
        await message.answer("❌ 系统错误。")
        return

    bots = await mgr.db.get_bots_by_owner(owner_id)
    all_rules = []
    for bot in bots:
        rules = await mgr.db.get_keyword_replies(bot.id)
        for r in rules:
            all_rules.append((bot, r))

    if not all_rules:
        await message.answer("📭 没有关键词回复规则。使用 /add_keyword 添加。")
        return

    text = "🗑️ <b>请回复要删除的规则 ID：</b>\n\n"
    for bot, rule in all_rules:
        status = "✅" if rule.enabled else "❌"
        text += (
            f"{status} ID={rule.id} [@{bot.bot_username}] "
            f"<code>{rule.keyword}</code> → {rule.reply_text[:30]}...\n"
        )
    text += "\n发送 /cancel 取消"

    await state.set_data({"del_rules": [(r.id, b.id) for b, r in all_rules]})
    await state.set_state(KeywordStates.waiting_for_delete)
    await message.answer(text)


@router.message(KeywordStates.waiting_for_delete, Command("cancel"))
async def cmd_del_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ 已取消。")


@router.message(KeywordStates.waiting_for_delete)
async def process_del_keyword(message: Message, state: FSMContext):
    """处理删除关键词"""
    data = await state.get_data()
    rule_ids = [r[0] for r in data.get("del_rules", [])]
    await state.clear()

    try:
        rule_id = int(message.text.strip())
    except (ValueError, TypeError):
        await message.answer("❌ 请输入有效的规则 ID。")
        return

    if rule_id not in rule_ids:
        await message.answer("❌ 无效的规则 ID，请重新使用 /del_keyword 查看。")
        return

    mgr = get_bot_manager()
    deleted = await mgr.db.delete_keyword_reply(rule_id)
    if deleted:
        await message.answer(f"✅ 规则 ID={rule_id} 已删除。")
    else:
        await message.answer(f"❌ 删除失败，规则 ID={rule_id} 不存在。")


# ==================== /toggle_keyword 启用/禁用关键词 ====================
@router.message(Command("toggle_keyword", "togglekeyword"))
async def cmd_toggle_keyword(message: Message, state: FSMContext):
    """启用/禁用关键词回复规则"""
    owner_id = message.from_user.id
    mgr = get_bot_manager()
    if not mgr:
        await message.answer("❌ 系统错误。")
        return

    bots = await mgr.db.get_bots_by_owner(owner_id)
    all_rules = []
    for bot in bots:
        rules = await mgr.db.get_keyword_replies(bot.id)
        for r in rules:
            all_rules.append((bot, r))

    if not all_rules:
        await message.answer("📭 没有关键词回复规则。使用 /add_keyword 添加。")
        return

    text = "🔄 <b>请回复要切换状态的规则 ID：</b>\n\n"
    for bot, rule in all_rules:
        status = "✅已启用" if rule.enabled else "❌已禁用"
        text += (
            f"[{rule.id}] {status} [@{bot.bot_username}] "
            f"<code>{rule.keyword}</code>\n"
        )
    text += "\n发送 /cancel 取消"

    await state.set_data({"toggle_rules": [(r.id, b.id) for b, r in all_rules]})
    await state.set_state(KeywordStates.waiting_for_toggle)
    await message.answer(text)


@router.message(KeywordStates.waiting_for_toggle, Command("cancel"))
async def cmd_toggle_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ 已取消。")


@router.message(KeywordStates.waiting_for_toggle)
async def process_toggle_keyword(message: Message, state: FSMContext):
    """处理切换关键词状态"""
    data = await state.get_data()
    rule_map = {r[0]: r[1] for r in data.get("toggle_rules", [])}
    await state.clear()

    try:
        rule_id = int(message.text.strip())
    except (ValueError, TypeError):
        await message.answer("❌ 请输入有效的规则 ID。")
        return

    if rule_id not in rule_map:
        await message.answer("❌ 无效的规则 ID，请重新使用 /toggle_keyword 查看。")
        return

    mgr = get_bot_manager()
    # 获取当前规则来确认状态
    rules = await mgr.db.get_keyword_replies(rule_map[rule_id])
    current_rule = next((r for r in rules if r.id == rule_id), None)
    if not current_rule:
        await message.answer("❌ 规则不存在。")
        return

    new_status = not current_rule.enabled
    success = await mgr.db.toggle_keyword_reply(rule_id, new_status)
    if success:
        status_text = "✅ 已启用" if new_status else "❌ 已禁用"
        await message.answer(f"✅ 规则 ID={rule_id} {status_text}")
    else:
        await message.answer("❌ 操作失败。")


# ==================== 通用取消 ====================
@router.message(KeywordStates.waiting_for_keyword, Command("cancel"))
@router.message(KeywordStates.waiting_for_reply, Command("cancel"))
@router.message(KeywordStates.waiting_for_mode, Command("cancel"))
async def cmd_cancel_any(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ 已取消。")