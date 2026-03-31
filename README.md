# 🤖 TG Bot 托管 & 私聊助手平台

基于 **Telegram + aiogram 3.x** 的多租户 Bot 托管 + 插件化 AI 助手平台。

用户通过主控 Bot 提交自己的 Bot Token，即可拥有一个 **AI 私聊助手 Bot**，支持 OpenAI 兼容接口（可自定义 API URL）。

---

## ✨ 功能特性

- 🤖 **多Bot管理** — 通过主Bot添加/删除/启停多个子Bot
- 🔐 **权限隔离** — 每个Bot仅限 owner 使用
- 🧠 **AI对话** — 支持 OpenAI 兼容接口，可自定义 API URL
- 🧩 **插件系统** — 可扩展的插件链，按优先级执行
- 💾 **对话记忆** — 自动保存对话历史，支持上下文连续对话
- 🗄️ **数据库兼容** — 默认 SQLite，后期可无缝切换 MySQL
- 🐳 **Docker部署** — 一键 Docker Compose 部署

---

## 📁 项目结构

```
bottoken/
├── main.py                     # 入口文件
├── .env.example                # 配置模板
├── requirements.txt            # Python 依赖
├── Dockerfile                  # Docker 镜像
├── docker-compose.yml          # Docker Compose 编排（Polling 模式）
├── docker-compose.webhook.yml  # Docker Compose 编排（Webhook 模式）
│
├── config/
│   ├── __init__.py
│   └── settings.py             # 配置管理（读取 .env）
│
├── database/
│   ├── __init__.py             # 数据库工厂函数
│   ├── base.py                 # 数据库抽象基类
│   ├── models.py               # 数据模型（Bot/BotConfig/Conversation）
│   └── sqlite_db.py            # SQLite 实现
│
├── bot_manager/
│   ├── __init__.py
│   └── manager.py              # Bot 生命周期管理核心
│
├── plugins/
│   ├── __init__.py
│   ├── base.py                 # 插件基类 + 插件链
│   ├── auth.py                 # 权限校验插件
│   ├── command.py              # 命令处理插件
│   ├── ai.py                   # AI 对话插件
│   ├── forward.py              # 消息转发插件
│   └── reply.py                # 统一回复插件
│
├── handlers/
│   ├── __init__.py
│   └── master.py               # 主Bot命令处理器
│
└── services/
    └── __init__.py              # 服务层（预留）
```

---

## 🚀 快速开始

### 前置条件

- Python 3.9+
- 一个 Telegram 主控 Bot Token（从 [@BotFather](https://t.me/BotFather) 获取）
- （可选）OpenAI API Key 或兼容接口

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd bottoken
```

### 2. 创建配置文件

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的配置：

```env
# 必填：主Bot Token
MASTER_BOT_TOKEN=123456:ABC-DEF_your_token_here

# 运行模式（开发用 polling，生产用 webhook）
BOT_MODE=polling

# AI 配置（支持自定义 API URL，兼容各种 OpenAI 中转服务）
AI_API_KEY=sk-your-api-key
AI_API_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-3.5-turbo
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行

```bash
python main.py
```

看到以下输出说明启动成功：

```
==================================================
TG Bot 托管平台 启动中...
==================================================
初始化数据库 (sqlite)...
数据库初始化完成
从数据库加载 0 个活跃Bot
已加载 0 个子Bot
使用 Polling 模式启动...
🚀 平台已启动！共 1 个Bot正在运行
按 Ctrl+C 停止
```

---

## 🐳 Docker 部署

### 方式一：Docker Compose（推荐）

```bash
# 1. 创建配置文件
cp .env.example .env
# 编辑 .env 填入你的配置

# 2. 构建并启动
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止
docker-compose down
```

### 方式二：手动 Docker

```bash
# 构建镜像
docker build -t tg-bot-platform .

# 运行
docker run -d \
  --name tg-bot-platform \
  --restart unless-stopped \
  --env-file .env \
  -v bot-data:/app/data \
  tg-bot-platform
```

---

## 🌐 Webhook 部署（生产推荐）

Webhook 模式适合生产环境，相比 Polling 模式有以下优势：

| 特性 | Polling 模式 | Webhook 模式 |
|------|-------------|-------------|
| 网络要求 | 需要能访问 Telegram API | 需要公网 HTTPS 域名 |
| 资源消耗 | 持续轮询，占用较多 | 按需推送，更节省资源 |
| 实时性 | 有轮询间隔延迟 | 即时推送，无延迟 |
| 稳定性 | 网络波动可能丢消息 | Telegram 保证送达 |
| 适用场景 | 开发测试 | **生产环境推荐** |

### 架构说明

```
Telegram 服务器
    │
    │ HTTPS POST (webhook)
    ▼
┌─────────────┐
│ 你的 Nginx   │ ← SSL 终止（由你自行配置）
│  反向代理    │
└─────┬───────┘
      │ HTTP 转发
      ▼
┌─────────────┐
│  Bot 容器    │ ← 8081 端口，aiohttp 服务器
│ (aiohttp)   │
└─────────────┘
```

### Webhook 路由

| 路径 | 说明 |
|------|------|
| `POST /webhook/master` | 主Bot接收消息 |
| `POST /webhook/sub/{bot_id}` | 子Bot接收消息 |
| `GET /health` | 健康检查 |

### 步骤一：配置 .env

```bash
cp .env.example .env
```

编辑 `.env`，关键配置：

```env
# 运行模式改为 webhook
BOT_MODE=webhook

# 你的 HTTPS 域名（Nginx 反向代理后的外部地址，Telegram 会往这里推送消息）
WEBHOOK_HOST=https://bot.yourdomain.com

# 容器内部监听端口，Docker 会把这个端口暴露到宿主机
# 你的 Nginx 反向代理应该指向 127.0.0.1:8081（即这个端口）
# 一般不需要修改
WEBHOOK_PORT=8081

# Webhook 基础路径
WEBHOOK_PATH=/webhook

# Webhook 密钥（强烈建议设置！用于验证请求来自 Telegram，防止伪造）
# 在终端运行 openssl rand -hex 32 生成随机字符串，然后粘贴到这里
WEBHOOK_SECRET=你生成的随机字符串

# 其他必填配置...
MASTER_BOT_TOKEN=your_master_bot_token
AI_API_KEY=your_api_key
```

### 步骤二：启动容器

```bash
# 使用 webhook 专用 compose 文件启动（暴露 8081 端口）
docker-compose -f docker-compose.webhook.yml up -d

# 查看日志
docker-compose -f docker-compose.webhook.yml logs -f
```

正常启动后会看到：

```
设置主Bot webhook: https://bot.yourdomain.com/webhook/master
🌐 Webhook 服务器已启动，监听端口 8081
🚀 平台已启动！共 1 个Bot正在运行 (webhook模式)
```

### 步骤三：配置 Nginx 反向代理

在你的 Nginx 中添加反向代理配置，将 webhook 请求转发到容器：

```nginx
server {
    listen 443 ssl http2;
    server_name bot.yourdomain.com;

    # 你的 SSL 证书配置
    ssl_certificate     /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    # Webhook 路径转发到容器
    location /webhook {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # 健康检查（可选）
    location /health {
        proxy_pass http://127.0.0.1:8081;
    }
}
```

> 💡 如果你使用 Caddy 或其他反向代理，只需将 `/webhook` 和 `/health` 路径转发到 `127.0.0.1:8081` 即可。

### 步骤四：验证

```bash
# 健康检查
curl https://bot.yourdomain.com/health

# 预期返回：
# {"status": "ok", "mode": "webhook", "active_bots": 0}

# 查看主Bot webhook 信息（需要替换 token）
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"
```

### 动态管理子Bot

在 webhook 模式下，通过主Bot添加新子Bot时会自动完成：

1. 注册 Bot 到 BotManager
2. 向 Telegram 注册 webhook URL（`/webhook/sub/{bot_id}`）
3. 后续该 Bot 的消息会通过 webhook 推送

无需重启服务，动态生效。

### 不使用 Docker 的 Webhook 部署

如果你直接在服务器上运行：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 .env（BOT_MODE=webhook）
cp .env.example .env

# 3. 使用 systemd 管理进程
cat > /etc/systemd/system/tg-bot.service << 'EOF'
[Unit]
Description=TG Bot Platform
After=network.target

[Service]
Type=simple
User=www
WorkingDirectory=/path/to/bottoken
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 4. 启动
systemctl enable tg-bot
systemctl start tg-bot

# 5. 在你的 Nginx 中配置反向代理，将 /webhook 转发到 127.0.0.1:8081
```

---

## 📖 使用说明

### 主Bot命令

在 Telegram 中向你的**主控Bot**发送以下命令：

| 命令 | 说明 |
|------|------|
| `/start` | 查看欢迎信息 |
| `/help` | 查看帮助 |
| `/add_bot` | 添加一个新的子Bot |
| `/my_bots` | 查看我的Bot列表 |
| `/delete_bot` | 删除Bot |
| `/start_bot` | 查看Bot运行状态 |
| `/stop_bot` | 停止Bot |

### 子Bot命令

添加成功后，向你的**子Bot**发送：

| 命令 | 说明 |
|------|------|
| `/start` | 查看欢迎信息 |
| `/help` | 帮助 |
| `/clear` | 清空对话记忆 |
| `/config` | 查看当前AI配置 |

直接发送任何文本消息即可与 AI 对话。

### 添加Bot流程

```
1. 在 @BotFather 创建新Bot，获取 Token
2. 向主控Bot发送 /add_bot
3. 按提示粘贴 Token
4. 系统自动校验 → 创建 → 启动
5. 向新Bot发消息即可开始AI对话 🎉
```

---

## ⚙️ 配置说明

### AI 接口配置

本项目支持任何 **OpenAI 兼容接口**，你可以自定义 `AI_API_BASE_URL`：

```env
# OpenAI 官方
AI_API_BASE_URL=https://api.openai.com/v1

# 自建中转
AI_API_BASE_URL=https://your-proxy.com/v1

# 其他兼容服务（如 one-api、new-api 等）
AI_API_BASE_URL=https://your-service.com/v1
```

### AI 参数配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `AI_TEMPERATURE` | `1.0` | 生成温度，控制随机性。值越低越确定，越高越随机。**注意：某些模型只支持特定值** |
| `AI_MAX_TOKENS` | `2000` | 单次回复最大 Token 数 |
| `AI_MODEL` | `gpt-3.5-turbo` | 使用的 AI 模型名称 |

> ⚠️ 部分中转服务的模型对 `temperature` 有严格限制（如只允许 `1`），如果遇到 400 错误请检查此项。

### 数据库配置

默认使用 SQLite，无需额外配置：

```env
DB_TYPE=sqlite
DB_SQLITE_PATH=./data/bot_platform.db
```

后期切换 MySQL（需实现 MySQL 驱动，已预留接口）：

```env
DB_TYPE=mysql
DB_MYSQL_HOST=localhost
DB_MYSQL_PORT=3306
DB_MYSQL_USER=root
DB_MYSQL_PASSWORD=your_password
DB_MYSQL_DATABASE=bot_platform
```

---

## 🧩 插件开发

### 创建自定义插件

在 `plugins/` 目录下创建新文件，继承 `BasePlugin`：

```python
# plugins/my_plugin.py
from plugins.base import BasePlugin, PluginResult, PluginContext
from aiogram import Bot
from aiogram.types import Message


class MyPlugin(BasePlugin):
    name = "my_plugin"    # 插件名称
    priority = 30          # 优先级（越小越先执行）

    async def on_message(self, bot: Bot, message: Message, context: PluginContext) -> PluginResult:
        # 你的处理逻辑
        if "hello" in message.text.lower():
            return PluginResult(
