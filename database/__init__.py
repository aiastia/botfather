"""
数据库模块
通过工厂函数根据配置创建对应的数据库实例
"""
from .base import DatabaseBase
from .models import Bot, BotConfig, Conversation


def create_database(db_type: str, **kwargs) -> DatabaseBase:
    """
    数据库工厂函数
    
    Args:
        db_type: 数据库类型 sqlite / mysql
        **kwargs: 数据库连接参数
    
    Returns:
        DatabaseBase 实例
    """
    if db_type == "sqlite":
        from .sqlite_db import SQLiteDatabase
        db_path = kwargs.get("db_path", "./data/bot_platform.db")
        return SQLiteDatabase(db_path)
    
    elif db_type == "mysql":
        # TODO: 后期实现 MySQL
        # from .mysql_db import MySQLDatabase
        # return MySQLDatabase(**kwargs)
        raise NotImplementedError("MySQL 支持尚未实现，请使用 SQLite")
    
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")