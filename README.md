# 🤖 养成系 AI 聊天机器人「牧之原翔子」

> 基于 [NoneBot2](https://nonebot.dev/) + OneBot V11（QQ）+ DeepSeek 的"养成系"聊天机器人。
>
> 角色「牧之原翔子」会记住你们之间的对话、积累好感度，随着关系从 **陌生人 → 朋友 → 挚友 → 羁绊** 逐渐亲近，语气也会随之变化；她还会主动早安晚安、偶尔触发随机小事件。

---

## 📑 目录

- [功能特性](#-功能特性)
- [项目结构](#-项目结构)
- [环境要求](#-环境要求)
- [快速开始](#-快速开始详细步骤)
- [命令与自动行为](#-命令与自动行为)
- [运行机制](#-运行机制)
- [配置说明](#-配置说明)
- [已知问题](#-已知问题)
- [参考](#-参考)

---

## ✨ 功能特性

- **自由聊天**：短期记忆（滑动窗口）+ 长期记忆（自动提炼重要事实）
- **养成系统**：好感度、经验、等级、心情、关系阶段
- **互动命令**：签到、喂食、陪玩、送礼物
- **定时任务**：每日早安 / 晚安、心情衰减、生日等特殊日期提醒
- **随机事件**：聊天时有概率触发，顺带加好感度

---

## 📁 项目结构

```
mybot/
├── pyproject.toml          # 依赖与 NoneBot 配置
├── bot.py                  # 入口文件（需自行创建，见快速开始第 4 步）
├── .env                    # 运行配置（OneBot 连接、数据库、API Key 等）
├── .env.dev / .env.prod    # 分环境配置
├── data.db                 # SQLite 数据库（首次运行自动生成）
└── src/plugins/
    ├── chatbot.py          # 聊天主逻辑（拼 prompt、调 DeepSeek）
    ├── chat_memory.py      # 短期对话记忆（存 / 取数据库）
    ├── user_memory.py      # 长期记忆 + 记忆提炼
    ├── user_growth.py      # 好感度档案 + 关系阶段
    ├── interaction.py      # 签到/喂食/陪玩/送礼物 + 随机事件
    └── time_event.py       # 定时任务（早安晚安、心情衰减、生日）
```

---

## 🔧 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | 3.10 – 3.12（在 3.12 上验证通过） |
| DeepSeek API Key | 在 [platform.deepseek.com](https://platform.deepseek.com) 申请 |
| QQ + OneBot 实现 | 一个 QQ 账号当机器人 + [NapCat](https://github.com/NapNeko/NapCatQQ) / [LLOneBot](https://github.com/LLOneBot/LLOneBot) / [Lagrange](https://github.com/LagrangeDev/Lagrange.Core) 等任意 OneBot V11 实现 |

---

## 🚀 快速开始（详细步骤）

### 第 1 步：安装依赖

```bash
cd mybot

# 创建并激活虚拟环境（Windows PowerShell）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装 pyproject.toml 里声明的依赖
pip install -e .

# openai 包被代码引用（用于调用 DeepSeek），但没写进 pyproject，需手动安装
pip install openai
```

> 可选：`pip install nb-cli` 提供 `nb` 命令，方便用 `nb run --reload` 热重载运行。

### 第 2 步：配置 `.env`

打开 [.env](.env)，把其中的 `DEEPSEEK_API_KEY` 换成**你自己的 Key**：

```dotenv
DEEPSEEK_API_KEY="sk-你的DeepSeekKey"
```

其余配置项（OneBot 连接、数据库等）按需修改，详见下方 [配置说明](#-配置说明)。

> ⚠️ `.env` 已加入 `.gitignore`，请勿把含 Key 的 `.env` 提交到公开仓库。

### 第 3 步：创建入口文件 `bot.py`

NoneBot2 需要一个入口文件，本项目未包含。在 `mybot/` 目录下新建 `bot.py`，内容如下：

```python
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)
nonebot.load_from_toml("pyproject.toml")

if __name__ == "__main__":
    nonebot.run()
```

### 第 4 步：启动 OneBot 实现

用 NapCat / LLOneBot / Lagrange 等登录你的 QQ 小号，并开启**正向 WebSocket**：

- 监听地址：`ws://127.0.0.1:3001`（与 `.env` 的 `ONEBOT_WS_URLS` 对应）
- Access Token：与 `.env` 的 `ONEBOT_ACCESS_TOKEN` 保持一致

### 第 5 步：启动机器人

```bash
# 方式一：直接运行入口
python bot.py

# 方式二：用 nb-cli（支持热重载，已装 nb-cli 时）
nb run --reload
```

首次运行会自动创建 `data.db` 及所需的表。看到日志里 OneBot 连接成功后即可使用。

### 第 6 步：验证

- **私聊**机器人：直接发消息（如「你好」）
- **群聊**：需要 @ 机器人
- 发「签到」应返回好感度变化

---

## 💬 命令与自动行为

### 互动命令

| 命令 | 别名 | 好感度 | 说明 |
| --- | --- | --- | --- |
| 签到 | 打卡 | +2 | 每天一次 |
| 喂食 | — | +3 | |
| 陪玩 | — | +4 | |
| 送礼物 <物品> | — | +5 | 例如 `/送礼物 巧克力`，会写入长期记忆 |
| 自由聊天 | — | +1 | 每发一条消息 +1 |

### 自动行为

| 时间 | 行为 |
| --- | --- |
| 每天 00:00 | 心情衰减（超过 1 天未互动则 -10，最低 0） |
| 每天 08:00 | 早安（文案按关系阶段变化） |
| 每天 20:00 | 晚安 |
| 每天 09:00 | 检查特殊日期（11/6 生日、元旦、圣诞） |

---

## 🧠 运行机制

- **关系阶段**（由好感度决定）：0 → 陌生人，50 → 朋友，150 → 挚友，300 → 羁绊
- **短期记忆**：每个用户保留最近约 20 条消息（`chatbot.py` 的 `MAX_HISTORY`）
- **长期记忆**：每聊 5 轮（`DISTILL_EVERY`）调用 DeepSeek 提炼一次，存进 `user_memory` 表；阶段越高，注入 prompt 的记忆条数越多（`STAGE_MEMORY_LIMIT`）
- **随机事件**：每次聊天 5% 概率触发（`interaction.py` 的 `RANDOM_EVENT_PROB`）

---

## ⚙️ 配置说明

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ENVIRONMENT` | `dev` | 环境名，决定加载 `.env.dev` / `.env.prod` |
| `DRIVER` | `~fastapi+~httpx+~websockets` | 运行驱动 |
| `DEEPSEEK_API_KEY` | — | DeepSeek API Key（**必填**，换成你自己的） |
| `ONEBOT_WS_URLS` | `ws://127.0.0.1:3001` | OneBot 正向 WebSocket 地址 |
| `ONEBOT_ACCESS_TOKEN` | — | 与 OneBot 实现里配置的 access token 一致 |
| `HOST` / `PORT` | `127.0.0.1` / `8080` | FastAPI 驱动监听地址 |
| `SUPERUSERS` | `["2462238357"]` | 超级用户 QQ 号（`time_event.py` 里的 `BOT_ID` 也要改成同一个号） |
| `COMMAND_START` | `["/", ""]` | 命令前缀（支持 `/` 或无前缀） |
| `SQLALCHEMY_DATABASE_URL` | `sqlite+aiosqlite:///data.db` | 数据库地址，一般不用改 |
| `LOCALSTORE_*` | 机器相关绝对路径 | 换机器需修改或删除（删掉会用默认目录） |

---

## ⚠️ 已知问题

1. `openai` 依赖未写入 `pyproject.toml`，需要手动 `pip install openai`（见快速开始第 1 步）。
2. 缺少入口文件 `bot.py`，需要按快速开始第 3 步自行创建。
3. `.env` 里的 `LOCALSTORE_*` 是机器相关的绝对路径，换机器需修改或删除。

---

## 📚 参考

- [NoneBot2 文档](https://nonebot.dev/)
- [OneBot V11 适配器](https://github.com/nonebot/adapter-onebot)
- [DeepSeek API 文档](https://api-docs.deepseek.com/)
