"""
SQLite 数据库实现
通过抽象基类接口，后期可无缝切换 MySQL
"""
import os
import logging
from typing import Optional, List
from datetime import datetime
import aiosqlite

from .base import DatabaseBase
from .models import Bot, BotConfig, Conversation

logger = logging.getLogger(__name__)

# SQL建表语句
CREATE_BOTS_TABLE = """
CREATE TABLE IF NOT EXISTS bots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    bot_token TEXT NOT NULL,
    bot_id INTEGER NOT NULL DEFAULT 0,
    bot_username TEXT NOT NULL DEFAULT '',
    bot_firstname TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_BOT_CONFIGS_TABLE = """
CREATE TABLE IF NOT EXISTS bot_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL UNIQUE,
    ai_enabled INTEGER NOT NULL DEFAULT 0,
    ai_model TEXT NOT NULL DEFAULT 'gpt-3.5-turbo',
    ai_temperature REAL NOT NULL DEFAULT 0.7,
    ai_max_tokens INTEGER NOT NULL DEFAULT 2000,
    ai_system_prompt TEXT NOT NULL DEFAULT '你是一个友好的AI助手。',
    ai_api_key TEXT NOT NULL DEFAULT '',
    ai_api_base_url TEXT NOT NULL DEFAULT '',
    custom_config TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (bot_id) REFERENCES bots(id)
);
"""

CREATE_CONVERSATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (bot_id) REFERENCES bots(id)
);
"""

CREATE_INDEX_OWNER = """
CREATE INDEX IF NOT EXISTS idx_bots_owner_id ON bots(owner_id);
"""

CREATE_INDEX_CONVERSATIONS = """
CREATE INDEX IF NOT EXISTS idx_conversations_bot_user ON conversations(bot_id, user_id);
"""


class SQLiteDatabase(DatabaseBase):
    """SQLite数据库实现"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """连接数据库"""
        # 确保目录存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        # 开启WAL模式提升并发性能
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        logger.info(f"SQLite 数据库已连接: {self.db_path}")

    async def close(self):
        """关闭数据库连接"""
        if self._db:
            await self._db.close()
            logger.info("SQLite 数据库已关闭")

    async def init_tables(self):
        """初始化数据库表"""
        await self._db.executescript(
            CREATE_BOTS_TABLE
            + CREATE_BOT_CONFIGS_TABLE
            + CREATE_CONVERSATIONS_TABLE
            + CREATE_INDEX_OWNER
            + CREATE_INDEX_CONVERSATIONS
        )
        await self._db.commit()
        logger.info("数据库表初始化完成")

    # ==================== Bot 操作 ====================
    async def add_bot(self, bot: Bot) -> int:
        now = datetime.now().isoformat()
        async with self._db.execute(
            """INSERT INTO bots (owner_id, bot_token, bot_id, bot_username, bot_firstname, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (bot.owner_id, bot.bot_token, bot.bot_id, bot.bot_username,
             bot.bot_firstname, bot.status, now, now),
        ) as cursor:
            await self._db.commit()
            return cursor.lastrowid

    async def get_bot(self, bot_id: int) -> Optional[Bot]:
        async with self._db.execute(
            "SELECT * FROM bots WHERE id = ? AND status != 'deleted'", (bot_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Bot.from_row(dict(row))
        return None

    async def get_bot_by_token(self, token: str) -> Optional[Bot]:
        async with self._db.execute(
            "SELECT * FROM bots WHERE bot_token = ? AND status != 'deleted'", (token,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Bot.from_row(dict(row))
        return None

    async def get_bots_by_owner(self, owner_id: int) -> List[Bot]:
        async with self._db.execute(
            "SELECT * FROM bots WHERE owner_id = ? AND status != 'deleted' ORDER BY created_at DESC",
            (owner_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [Bot.from_row(dict(row)) for row in rows]

    async def get_all_active_bots(self) -> List[Bot]:
        async with self._db.execute(
            "SELECT * FROM bots WHERE status = 'active' ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [Bot.from_row(dict(row)) for row in rows]

    async def update_bot_status(self, bot_id: int, status: str):
        now = datetime.now().isoformat()
        await self._db.execute(
            "UPDATE bots SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, bot_id),
        )
        await self._db.commit()

    async def delete_bot(self, bot_id: int):
        await self.update_bot_status(bot_id, "deleted")

    # ==================== BotConfig 操作 ====================
    async def get_bot_config(self, bot_id: int) -> Optional[BotConfig]:
        async with self._db.execute(
            "SELECT * FROM bot_configs WHERE bot_id = ?", (bot_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return BotConfig.from_row(dict(row))
        return None

    async def create_bot_config(self, config: BotConfig) -> int:
        now = datetime.now().isoformat()
        async with self._db.execute(
            """INSERT INTO bot_configs
               (bot_id, ai_enabled, ai_model, ai_temperature, ai_max_tokens,
                ai_system_prompt, ai_api_key, ai_api_base_url, custom_config, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (config.bot_id, int(config.ai_enabled), config.ai_model,
             config.ai_temperature, config.ai_max_tokens, config.ai_system_prompt,
             config.ai_api_key, config.ai_api_base_url, config.custom_config, now, now),
        ) as cursor:
            await self._db.commit()
            return cursor.lastrowid

    async def update_bot_config(self, config: BotConfig):
        now = datetime.now().isoformat()
        await self._db.execute(
            """UPDATE bot_configs SET
               ai_enabled = ?, ai_model = ?, ai_temperature = ?, ai_max_tokens = ?,
               ai_system_prompt = ?, ai_api_key = ?, ai_api_base_url = ?,
               custom_config = ?, updated_at = ?
               WHERE bot_id = ?""",
            (int(config.ai_enabled), config.ai_model, config.ai_temperature,
             config.ai_max_tokens, config.ai_system_prompt, config.ai_api_key,
             config.ai_api_base_url, config.custom_config, now, config.bot_id),
        )
        await self._db.commit()

    # ==================== Conversation 操作 ====================
    async def add_conversation(self, conv: Conversation) -> int:
        now = datetime.now().isoformat()
        async with self._db.execute(
            """INSERT INTO conversations (bot_id, user_id, role, content, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (conv.bot_id, conv.user_id, conv.role, conv.content, now),
        ) as cursor:
            await self._db.commit()
            return cursor.lastrowid

    async def get_conversations(self, bot_id: int, user_id: int, limit: int = 20) -> List[Conversation]:
        async with self._db.execute(
            """SELECT * FROM conversations
               WHERE bot_id = ? AND user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (bot_id, user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            # 按时间正序返回（最新的在最后）
            result = [Conversation.from_row(dict(row)) for row in reversed(rows)]
            return result

    async def clear_conversations(self, bot_id: int, user_id: int):
        await self._db.execute(
            "DELETE FROM conversations WHERE bot_id = ? AND user_id = ?",
            (bot_id, user_id),
        )
        await self._db.commit()