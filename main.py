
import asyncio
import hmac
import logging
import sys
from typing import Optional

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

from config.settings import settings
from database import create_database
from database.base import DatabaseBase
from bot_manager.manager import BotManager
from handlers.master import router as master_router, register_bot_commands

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

    # 6. 注册 Telegram 命令菜单
    await register_bot_commands(master_bot)

    # 7. 启动模式
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


# ==================== Webhook 模式 ====================

def _verify_webhook_secret(token: str, secret_header: Optional[str]) -> bool:
    """
    验证 Telegram webhook 请求的 secret_token
    Telegram 会在 X-Telegram-Bot-Api-Secret-Token 头中发送我们设置的密钥
    """
    if not settings.WEBHOOK_SECRET:
        return True  # 未配置密钥则跳过验证
    if not secret_header:
        return False
    return hmac.compare_digest(settings.WEBHOOK_SECRET, secret_header)


async def _process_webhook_update(
    bot: Bot, dispatcher: Dispatcher, update_json: dict
) -> bool:
    """将 webhook 收到的 Update 分发给对应的 Dispatcher 处理"""
    try:
        update = Update.model_validate(update_json)
        await dispatcher.feed_update(bot, update)
        return True
    except Exception as e:
        logger.error(f"处理 webhook update 失败: {e}", exc_info=True)
        return False


async def webhook_master_handler(request: web.Request) -> web.Response:
    """主Bot webhook 处理"""
    master_app = request.app["master_app"]
    master_bot: Bot = master_app["bot"]
    master_dp: Dispatcher = master_app["dp"]

    # 验证密钥
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not _verify_webhook_secret(master_bot.token, secret):
        logger.warning("主Bot webhook 密钥验证失败")
        return web.Response(status=403)

    try:
        update_json = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    success = await _process_webhook_update(master_bot, master_dp, update_json)
    return web.Response(status=200 if success else 500)


async def webhook_sub_handler(request: web.Request) -> web.Response:
    """子Bot webhook 处理"""
    bot_id_str = request.match_info.get("bot_id")
    if not bot_id_str:
        return web.Response(status=400, text="Missing bot_id")

    try:
        bot_id = int(bot_id_str)
    except ValueError:
        return web.Response(status=400, text="Invalid bot_id")

    mgr: BotManager = request.app["bot_manager"]
    all_bots = mgr.get_all_bots()

    managed = all_bots.get(bot_id)
    if not managed:
        logger.warning(f"Webhook 收到未知 bot_id={bot_id} 的请求")
        return web.Response(status=404, text="Bot not found")

    # 验证密钥
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not _verify_webhook_secret(managed.bot.token, secret):
        logger.warning(f"子Bot {bot_id} webhook 密钥验证失败")
        return web.Response(status=403)

    try:
        update_json = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    success = await _process_webhook_update(managed.bot, managed.dispatcher, update_json)
    return web.Response(status=200 if success else 500)


async def health_handler(request: web.Request) -> web.Response:
    """健康检查端点"""
    mgr: BotManager = request.app["bot_manager"]
    return web.json_response({
        "status": "ok",
        "mode": "webhook",
        "active_bots": mgr.active_count,
    })


async def _set_webhook(bot: Bot, webhook_url: str, drop_pending: bool = False):
    """为单个 Bot 设置 webhook"""
    secret = settings.WEBHOOK_SECRET or None
    result = await bot.set_webhook(
        url=webhook_url,
        secret_token=secret,
        drop_pending_updates=drop_pending,
        allowed_updates=["message"],
    )
    return result


async def _delete_webhook(bot: Bot):
    """删除 Bot 的 webhook"""
    await bot.delete_webhook(drop_pending_updates=True)


async def start_webhook(master_bot: Bot, master_dp: Dispatcher, mgr: BotManager):
    """Webhook 模式启动"""
    logger.info("使用 Webhook 模式启动...")

    # 1. 创建 aiohttp 应用
    app = web.Application()

    # 存储 master bot 和 dispatcher
    app["master_app"] = {"bot": master_bot, "dp": master_dp}
    app["bot_manager"] = mgr

    # 2. 注册路由
    base_path = settings.WEBHOOK_PATH.rstrip("/")

    # 主Bot webhook: /webhook/master
    app.router.add_post(f"{base_path}/master", webhook_master_handler)

    # 子Bot webhook: /webhook/sub/{bot_id}
    app.router.add_post(f"{base_path}/sub/{{bot_id}}", webhook_sub_handler)

    # 健康检查
    app.router.add_get("/health", health_handler)

    # 3. 设置所有 Bot 的 webhook
    master_webhook_url = settings.webhook_url
    logger.info(f"设置主Bot webhook: {master_webhook_url}")
    await _set_webhook(master_bot, master_webhook_url, drop_pending=True)

    for bot_id, managed in mgr.get_all_bots().items():
        sub_url = settings.sub_webhook_url_template.format(bot_id=bot_id)
        logger.info(f"设置子Bot {bot_id} webhook: {sub_url}")
        await _set_webhook(managed.bot, sub_url, drop_pending=True)

    # 4. 启动 aiohttp 服务器
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.WEBHOOK_PORT)
    await site.start()

    logger.info(f"🌐 Webhook 服务器已启动，监听端口 {settings.WEBHOOK_PORT}")
    logger.info(f"   主Bot webhook: {master_webhook_url}")
    logger.info(f"   子Bot webhook 模板: {settings.sub_webhook_url_template}")
    logger.info(f"   健康检查: http://0.0.0.0:{settings.WEBHOOK_PORT}/health")
    logger.info(f"🚀 平台已启动！共 {1 + mgr.active_count} 个Bot正在运行 (webhook模式)")
    logger.info("按 Ctrl+C 停止")

    # 5. 保持运行
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("正在停止...")
    finally:
        # 清理：删除所有 webhook
        logger.info("清理 webhook...")
        try:
            await _delete_webhook(master_bot)
            for bot_id, managed in mgr.get_all_bots().items():
                await _delete_webhook(managed.bot)
        except Exception as e:
            logger.error(f"清理 webhook 失败: {e}")
        await runner.cleanup()
        await shutdown(master_bot, mgr)


# ==================== 关闭 ====================

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
