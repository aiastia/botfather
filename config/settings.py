"""
配置管理模块
从 .env 文件加载配置，支持环境变量覆盖
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    """全局配置类"""

    # ==================== 主Bot配置 ====================
    MASTER_BOT_TOKEN: str = os.getenv("MASTER_BOT_TOKEN", "")

    # ==================== 运行模式 ====================
    BOT_MODE: str = os.getenv("BOT_MODE", "polling")  # polling / webhook

    # ==================== Webhook配置 ====================
    WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "https://your-domain.com")
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8443"))
    WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")

    @property
    def webhook_url(self) -> str:
        return f"{self.WEBHOOK_HOST}{self.WEBHOOK_PATH}"

    # ==================== 数据库配置 ====================
    DB_TYPE: str = os.getenv("DB_TYPE", "sqlite")  # sqlite / mysql
    DB_SQLITE_PATH: str = os.getenv("DB_SQLITE_PATH", "./data/bot_platform.db")

    # MySQL配置
    DB_MYSQL_HOST: str = os.getenv("DB_MYSQL_HOST", "localhost")
    DB_MYSQL_PORT: int = int(os.getenv("DB_MYSQL_PORT", "3306"))
    DB_MYSQL_USER: str = os.getenv("DB_MYSQL_USER", "root")
    DB_MYSQL_PASSWORD: str = os.getenv("DB_MYSQL_PASSWORD", "")
    DB_MYSQL_DATABASE: str = os.getenv("DB_MYSQL_DATABASE", "bot_platform")

    @property
    def db_url(self) -> str:
        if self.DB_TYPE == "mysql":
            return (
                f"mysql+aiomysql://{self.DB_MYSQL_USER}:{self.DB_MYSQL_PASSWORD}"
                f"@{self.DB_MYSQL_HOST}:{self.DB_MYSQL_PORT}/{self.DB_MYSQL_DATABASE}"
            )
        return f"sqlite+aiosqlite:///{self.DB_SQLITE_PATH}"

    # ==================== AI配置 ====================
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_API_BASE_URL: str = os.getenv("AI_API_BASE_URL", "https://api.openai.com/v1")
    AI_MODEL: str = os.getenv("AI_MODEL", "gpt-3.5-turbo")
    AI_TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE", "0.7"))
    AI_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", "2000"))

    # ==================== 日志配置 ====================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ==================== 加密配置（预留） ====================
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")  # AES加密密钥，预留

    def validate(self) -> list:
        """校验必要配置，返回错误列表"""
        errors = []
        if not self.MASTER_BOT_TOKEN:
            errors.append("MASTER_BOT_TOKEN 未配置")
        if self.BOT_MODE not in ("polling", "webhook"):
            errors.append("BOT_MODE 必须为 polling 或 webhook")
        if self.BOT_MODE == "webhook" and not self.WEBHOOK_HOST.startswith("https"):
            errors.append("Webhook 模式需要 HTTPS 域名")
        return errors


# 全局配置实例
settings = Settings()