"""
插件系统基类
定义插件接口、执行结果、上下文等核心结构
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from aiogram import Bot
from aiogram.types import Message


@dataclass
class PluginResult:
    """
    插件执行结果
    
    Attributes:
        stop: 是否终止后续插件执行（中断链）
        reply_text: 需要回复给用户的文本
        handled: 是否已处理该消息
    """
    stop: bool = False
    reply_text: str = ""
    handled: bool = False


@dataclass
class PluginContext:
    """
    插件上下文，用于插件间通信和状态共享
    
    Attributes:
        bot_record: 数据库中的Bot记录
        bot_config: Bot配置
        user_id: 当前用户ID
        context: 自定义上下文数据
    """
    bot_record: Any = None  # database.models.Bot
    bot_config: Any = None  # database.models.BotConfig
    user_id: int = 0
    context: Dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any):
        """设置上下文值"""
        self.context[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文值"""
        return self.context.get(key, default)


class BasePlugin:
    """
    插件基类
    
    所有插件必须继承此类并实现 on_message 方法。
    插件按 priority 排序执行，数值越小优先级越高。
    
    Attributes:
        name: 插件名称
        priority: 执行优先级（数值越小越先执行）
    """
    name: str = "base"
    priority: int = 100

    async def on_message(
        self,
        bot: Bot,
        message: Message,
        context: PluginContext,
    ) -> PluginResult:
        """
        处理消息
        
        Args:
            bot: aiogram Bot 实例
            message: Telegram 消息对象
            context: 插件上下文
        
        Returns:
            PluginResult 执行结果
        """
        return PluginResult()

    async def on_start(self):
        """插件启动时调用（可选）"""
        pass

    async def on_stop(self):
        """插件停止时调用（可选）"""
        pass

    def __repr__(self):
        return f"<Plugin:{self.name}(priority={self.priority})>"


class PluginChain:
    """
    插件链管理器
    负责插件的注册、排序和链式执行
    """

    def __init__(self):
        self._plugins: list = []

    def register(self, plugin: BasePlugin):
        """注册插件"""
        self._plugins.append(plugin)
        # 按优先级排序
        self._plugins.sort(key=lambda p: p.priority)

    def unregister(self, name: str):
        """按名称移除插件"""
        self._plugins = [p for p in self._plugins if p.name != name]

    def get_plugins(self) -> list:
        """获取所有已注册插件"""
        return self._plugins

    async def execute(
        self,
        bot: Bot,
        message: Message,
        context: PluginContext,
    ) -> PluginResult:
        """
        链式执行所有插件
        
        当某个插件返回 stop=True 时，终止后续执行。
        如果有插件设置了 reply_text，将会被返回。
        
        Returns:
            最终的 PluginResult
        """
        final_result = PluginResult()

        for plugin in self._plugins:
            try:
                result = await plugin.on_message(bot, message, context)

                # 累积回复文本
                if result.reply_text:
                    final_result.reply_text = result.reply_text
                if result.handled:
                    final_result.handled = True

                # 是否终止链
                if result.stop:
                    final_result.stop = True
                    break

            except Exception as e:
                # 插件执行错误不影响其他插件
                import logging
                logging.getLogger(__name__).error(
                    f"插件 {plugin.name} 执行错误: {e}", exc_info=True
                )
                continue

        return final_result

    async def start_all(self):
        """启动所有插件"""
        for plugin in self._plugins:
            try:
                await plugin.on_start()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"插件 {plugin.name} 启动错误: {e}", exc_info=True
                )

    async def stop_all(self):
        """停止所有插件"""
        for plugin in self._plugins:
            try:
                await plugin.on_stop()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"插件 {plugin.name} 停止错误: {e}", exc_info=True
                )