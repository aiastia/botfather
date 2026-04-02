"""
主Bot命令处理器
处理用户与主控Bot的基础交互，并聚合所有子模块路由
"""
import logging
from aiogram import Router, Bot
from aiogram.types import Message, BotCommand
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

router = Router()

# 引入子模块路由
from handlers.bot_manage import router as bot_manage_router
from handlers.bot_config import router as bot_config_router
from handlers.admin import router as admin_router

router.include_router(bot_manage_router)
router.include_router(bot_config_router)
router.include_router(admin_router)


# ==================== 启动时注册命令菜单 ====================
async def register_bot_commands(bot: Bot):
    """向 Telegram 注册 Bot 命令菜单（聊天框中显示的命令提示）"""
    commands = [
        BotCommand(command="add_bot", description="添加新 Bot"),
        BotCommand(command="my_bots", description="查看我的 Bot"),
        BotCommand(command="delete_bot", description="删除 Bot"),
        BotCommand(command="start_bot", description="查看 Bot 启动状态"),
        BotCommand(command="stop_bot", description="停止 Bot"),
        BotCommand(command="config", description="查看 Bot 配置"),
        BotCommand(command="setkey", description="设置 AI API Key"),
        BotCommand(command="setapi", description="设置 AI API URL"),
        BotCommand(command="setmodel", description="设置 AI 模型"),
        BotCommand(command="help", description="查看帮助"),
    ]
    await bot.set_my_commands(commands)
    logger.info("已注册 Bot 命令菜单")


# ==================== /start 命令 ====================
@router.message(Command("start"))
async def cmd_start(message: Message):
    """初始化 / 欢迎信息"""
    text = (
        "👋 <b>欢迎使用 TG Bot 托管平台！</b>\n\n"
        "我可以帮你管理多个 Telegram Bot，"
        "让每个 Bot 都变成你的 <b>AI 私聊助手</b>。\n\n"
        "📌 <b>快速开始：</b>\n"
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
        "📖 <b>使用帮助</b>\n\n"
        "<b>Bot 管理：</b>\n"
        "/add_bot - 添加新 Bot\n"
        "/my_bots - 查看我的 Bot\n"
        "/delete_bot - 删除 Bot\n"
        "/start_bot - 查看 Bot 状态\n"
        "/stop_bot - 停止 Bot\n\n"
        "<b>AI 配置（每个Bot可独立设置）：</b>\n"
        "/config - 查看 Bot 配置\n"
        "/setkey - 设置 AI API Key\n"
        "/setapi - 设置 AI API 地址\n"
        "/setmodel - 设置 AI 模型\n\n"
        "<b>💡 提示：</b>\n"
        "1. 先在 @BotFather 创建一个 Bot\n"
        "2. 使用 /add_bot 将其添加到平台\n"
        "3. 用户发给 Bot 的消息会自动转发给你\n"
        "4. 你可以直接回复转发消息来回复用户\n"
    )
    await message.answer(text)


# ==================== /cancel 命令（通用取消） ====================
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """通用取消"""
    await state.clear()
    await message.answer("❌ 操作已取消。")