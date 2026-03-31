"""
TG Bot 托管 & 私聊助手平台
主入口文件
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config.settings import settings
from database import create_database
from database.base import DatabaseBase
from bot_manager.manager import BotManager
from handlers.master import router as master_router

# 全局日志配置
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 全局 BotManager 实例（供 handlers 引用）
bot_manager: BotManager = None  # type: ignore


async def main():
    global bot_manager

    logger.info("=" * 50)
    logger.info("TG Bot 托管平台 启动中...")
    logger.info("=" * 50)

    # 1. 校验配置
    errors = settings.validate()
    if errors:
        for err in errors:
            logger.error(f"配置错误: {err}")
        logger.error("请检查 .env 配置文件")
        sys.exit(1)

    # 2. 初始化数据库
    logger.info(f"初始化数据库 ({settings.DB_TYPE})...")
    db = create_database(
        db_type=settings.DB_TYPE,
        db_path=settings.DB_SQLITE_PATH,
    )

    # 连接数据库（SQLite需要先connect）
    if hasattr(db, "connect"):
        await db.connect()
    await db.init_tables()
    logger.info("数据库初始化完成")

    # 3. 初始化 BotManager
    bot_manager = BotManager(db)

    # 4. 加载已有的Bot
    await bot_manager.load_all_bots()
    logger.info(f"已加载 {bot_manager.active_count} 个子Bot")

    # 5. 创建主Bot
    master_bot = Bot(
        token=settings.MASTER_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    master_dp = Dispatcher()
    master_dp.include_router(master_router)

    # 6. 启动模式
    if settings.BOT_MODE == "polling":
        await start_polling(master_bot, master_dp, bot_manager)
    elif settings.BOT_MODE == "webhook":
        await start_webhook(master_bot, master_dp, bot_manager)


async def start_polling(master_bot: Bot, master_dp: Dispatcher, mgr: BotManager):
    """Polling 模式启动"""
    logger.info("使用 Polling 模式启动...")

    # 同时运行主Bot和所有子Bot的polling
    tasks = []

    # 主Bot polling
    tasks.append(asyncio.create_task(
        master_dp.start_polling(master_bot, handle_signals=False),
        name="master_bot",
    ))

    # 子Bot polling
    for bot_id, managed in mgr.get_all_bots().items():
        tasks.append(asyncio.create_task(
            managed.dispatcher.start_polling(managed.bot, handle_signals=False),
            name=f"sub_bot_{bot_id}",
        ))
        logger.info(f"  子Bot polling 已启动")

    logger.info(f"🚀 平台已启动！共 {len(tasks)} 个Bot正在运行")
    logger.info("按 Ctrl+C 停止")

    try:
        # 等待所有任务
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, SystemExit):
        logger.info("正在停止...")
    finally:
        await shutdown(master_bot, mgr)


async def start_webhook(master_bot: Bot, master_dp: Dispatcher, mgr: BotManager):
    """Webhook 模式启动（预留）"""
    logger.info("使用 Webhook 模式启动...")
    # TODO: 实现 Webhook 模式
    # 需要 aiohttp 服务器来接收 webhook 请求
    logger.warning("Webhook 模式尚未完全实现，请使用 polling 模式")
    await start_polling(master_bot, master_dp, mgr)


async def shutdown(master_bot: Bot, mgr: BotManager):
    """优雅关闭"""
    logger.info("正在关闭所有Bot...")

    # 停止所有子Bot
    for bot_id in list(mgr.get_all_bots().keys()):
        await mgr.unregister_bot(bot_id)

    # 关闭主Bot
    session = master_bot.session
    if session and not session.closed:
        await session.close()

    logger.info("所有Bot已关闭，再见！")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已停止")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)