<div align="center">

# 虎牙每日自动助手 (Huya Daily Helper)

**纯 WUP/JCE 协议全自动打卡 · 粉丝团专属福利领取 · 智能赠送包裹虎粮 · 8 格极简黑白方块进度条推送 · Actions 全自动调度**

[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/995william/huya-gift/huya_gift.yml?branch=main&label=%E4%BB%BB%E5%8A%A1%E6%B5%81%E6%B0%B4%E7%BA%BF&logo=github)](https://github.com/995william/huya-gift/actions)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/995william/huya-gift?style=social)](https://github.com/995william/huya-gift)

</div>

---

## 📖 项目简介

本项目是专为**虎牙直播（Huya.com）**打造的自动化助手工具，实现每日自动完成粉丝团打卡（亲密度 +5）、移动端专属福利领取（每日 10 虎粮）、包裹免费虎粮库存查询及定向赠送给指定主播，并生成极其精致的移动端零折行黑白方块进度报告。

项目提供两种运行模式：
- ⚡ **v2（推荐 · 移动端纯协议版）**：采用纯 Python 原生实现的 JCE/WUP 协议直连官方网关（`wup.huya.com`），毫秒级完成状态校验、打卡与领粮送礼。**无需启动无头浏览器，零内存消耗，节省 90% 以上 Actions 运行时间**。
- 🌐 **v1（网页端兜底版）**：基于 Playwright 自动化驱动无头 Chromium 模拟真实用户行为，支持可视化的本地交互与登录。

---

## ✨ 核心特性

- 🚀 **纯原生 WUP/JCE 协议栈**：逆向解析并实现腾讯/虎牙底层 JCE 二进制序列化与 WUP 网关交互，实现免浏览器、超低延迟的纯协议调用。
- 🎁 **移动端专属福利领取**：自动请求并解析 `queryFansGroupTaskInfo` 与 `operateFansBox`，稳定领取移动端专属的每日 10 虎粮。
- 🏷️ **高精度勋章与亲密度计算**：实时提取当前主播的粉丝勋章等级（如 `Lv.12`）、升级所需经验及今日已获取亲密度进度。
- 🌾 **包裹免费虎粮智能赠送**：精准查询背包中即将过期的免费虎粮，支持指定赠送数量或一键清空背包，并在送礼后进行双向库存复查核销。
- 📱 **8 格黑白方块极简卡片**：专为移动端手机屏幕排版打造的 `[■■■■■□□□]` 视觉化进度条，全文本推送零折行、美观整洁。
- 📢 **多渠道执行报告推送**：支持企业微信群机器人 Webhook、企业微信自建应用，并无缝集成 GitHub Actions Job Summary 页面展示。
- ⏰ **云端全自动与无感保活**：每日北京时间 07:10 自动执行，并内置 GitHub 仓库活跃保活工作流，避免定时任务休眠停用。

---

## 📱 消息推送模板与视觉预览

任务执行完毕后，机器人将推送格式经过精密对齐的运行报告。

### 1. 运行完成通知效果（手机端零折行排版）

```text
【🐯 虎牙助手 · 运行报告】
──────────────
🚩 演示主播 (123456)
📱 138****1234 ｜ ✅ 完成

🏅 勋章：Lv.12 (徽章)
📊 [■■■■■□□□] 62.5%
📈 经验：1250 / 2000
⏳ 升级：还差 750 亲密度
🔥 今日：+15 / 500

📋 执行明细：
├ 签到：打卡成功 (+5)
├ 福利：已领 10 虎粮
├ 送礼：成功送出 10 个
└ 余量：0 个
──────────────
```

### 2. 局部完成 / 无余粮预览

```text
【🐯 虎牙助手 · 运行报告】
──────────────
🚩 演示主播 (123456)
📱 138****1234 ｜ ℹ️ 部分完成

🏅 勋章：Lv.5 (徽章)
📊 [■■□□□□□□] 25.0%
📈 经验：100 / 400
⏳ 升级：还差 300 亲密度
🔥 今日：+5 / 500

📋 执行明细：
├ 签到：打卡成功 (+5)
├ 福利：已领 10 虎粮
├ 送礼：无余粮跳过
└ 余量：0 个
──────────────
```

---

## 🚀 快速使用指南 (GitHub Actions 运行)

### 第一步：Fork 本仓库
点击仓库右上角 **Fork** 按钮，将本仓库复制到您个人的 GitHub 账号下。

> **开启工作流权限**（关键）：
> 进入 Fork 后的仓库，点击 **Settings** -> **Actions** -> **General**，在底部的 **Workflow permissions** 勾选 **Read and write permissions** 并点击 **Save**。

---

### 第二步：获取虎牙登录凭据 (Cookie)

#### 方法 A：使用内置脚本一键获取（最便捷）
在本地电脑执行以下命令，将自动弹出登录窗口，手机虎牙 App 扫码即可自动提取并生成配置好的 Cookie：
```bash
pip install -r requirements.txt
playwright install chromium
python tools/get_cookie.py
```

#### 方法 B：浏览器手动抓取
1. 在电脑浏览器登录 [虎牙直播个人中心](https://i.huya.com/)。
2. 按 `F12` 打开开发者工具，切换至 **Network (网络)** 标签页并刷新页面。
3. 复制任意请求中的 **Request Headers -> Cookie**。
   *(必须包含 `yyuid` 或 `udb_uid` 以及登录认证令牌)*

---

### 第三步：配置 GitHub Secrets 与 Variables

进入仓库的 **Settings** -> **Secrets and variables** -> **Actions**：

#### 1. 必要 Secrets 配置 (Repository secrets)
点击 **New repository secret** 添加：

| Secret 变量名 | 必填 | 说明 | 示例 |
| :--- | :---: | :--- | :--- |
| `HUYA_COOKIE` | **是** | 虎牙完整登录 Cookie | `yyuid=...; udb_biztoken=...;` |
| `HUYA_ROOM_URL` | **是** | **目标主播直播间地址**（打卡粉丝团与赠送虎粮的目标） | `https://www.huya.com/123456` *(填入您关注的主播房间)* |
| `WX_WEBHOOK` | 否 | 企业微信群机器人 Webhook 地址（全文本卡片推送） | 群机器人的完整 Webhook URL |

> 📌 **目标主播配置说明**：
> - 可以在 **Repository secrets** 中添加 `HUYA_ROOM_URL`（私密配置）；
> - 或者在 **Repository variables** 中添加 `HUYA_ROOM_URL`（随时方便查看修改）；
> - 格式为标准的虎牙直播间链接，例如 `https://www.huya.com/123456` 或带有房号别名的链接。脚本将自动通过官方 API 动态获取该主播的 PID 与元数据，绝不泄露任何主播私隐！

#### 2. 自定义运行选项 (Repository variables，可选)
在 **Variables** 标签页中按需配置覆盖：

| Variable 变量名 | 默认值 | 说明 |
| :--- | :---: | :--- |
| `HUYA_GIFT_COUNT` | `0` | 每次赠送虎粮数量（`0` 表示全部赠送，或指定数字如 `10`） |
| `HUYA_VERSION` | `v2` | 运行版本（`v2` 移动端纯协议版推荐，`v1` 网页端） |
| `HUYA_DAKA` | `true` | 是否执行每日粉丝团打卡（亲密度 +5） |
| `HUYA_WELFARE` | `true` | 是否领取移动端每日专属 10 虎粮 |
| `HUYA_WECHAT_PUSH` | `true` | 是否通过企业微信群机器人推送卡片报告 |

---

### 第四步：手动触发测试

1. 进入仓库顶部的 **Actions** 页面。
2. 在左侧选择 **虎牙每日助手** 工作流。
3. 点击右侧 **Run workflow** -> 点击绿色按钮即可手动执行一次任务。
4. 查看步骤日志，执行完毕后即可在企业微信中收到打卡与资产报告！

---

## 💻 本地调试运行

```bash
# 1. 克隆代码
git clone https://github.com/995william/huya-gift.git
cd huya-gift

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行助手 (必须指定目标主播房间，优先读取 HUYA_ROOM_URL 环境变量，亦可通过 --room 传入)
python main.py --version v2 --room https://www.huya.com/123456 --count 0

# 常用命令参数：
# python main.py --room https://www.huya.com/123456 --no-daka --no-welfare     # 只送礼不打卡
# python main.py --room https://www.huya.com/123456 --no-wechat-push            # 禁用企业微信推送
# python tools/claim_food.py --pid 123456 --dry-run                           # 独立查询每日 10 虎粮状态
# python tools/ad_helper.py --pid 123456 --rounds 3                           # 运行广告领虎粮辅助
```

---

## 📂 项目结构说明

```text
huya-gift/
├── .github/
│   └── workflows/
│       ├── huya_gift.yml            # 每日定时执行流水线（Cron: 10 23 * * *）
│       └── keepalive.yml            # 仓库活跃状态保活工作流
├── core/                            # 核心业务与协议引擎
│   ├── __init__.py
│   ├── common.py                    # 公共基础库（日志、脱敏、进度条、房间解析与推送中心）
│   ├── wup.py                       # 核心底层：WUP/JCE 二进制编解码器与网关驱动
│   ├── mobile_bot.py                # v2 移动端纯协议打卡、领粮、送粮实现
│   └── web_bot.py                   # v1 网页端 Playwright 浏览器自动化实现
├── tools/                           # 辅助工具脚本
│   ├── __init__.py
│   ├── get_cookie.py                # 本地扫码/登录提取 Cookie 工具
│   ├── claim_food.py                # 独立领取每日 10 虎粮工具
│   └── ad_helper.py                 # 人工看广告领虎粮辅助核对工具
├── main.py                          # 统一命令行主入口与调度器
├── requirements.txt                 # 项目依赖
└── README.md                        # 项目使用与架构指南
```

---

## ❓ 常见问题 (FAQ)

<details>
<summary><b>Q1: 为什么推荐使用 v2 而不是 v1？</b></summary>
v2 采用原生 Python 直接和官方 WUP 接口通信，无需下载与启动数百兆的 Chromium 浏览器，执行时间通常在 3 秒以内，极大节省了资源与 GitHub Actions 的免费构建时长。
</details>

<details>
<summary><b>Q2: Cookie 会经常过期吗？</b></summary>
虎牙的登录态通常可维持 1~3 个月以上。只要您不主动在抓取过 Cookie 的网页或 App 上点击「退出登录」，凭据即可长期有效。
</details>

<details>
<summary><b>Q3: 定时执行的时间是什么时候？</b></summary>
工作流默认配置的 Cron 是 <code>10 23 * * *</code>（UTC 23:10），对应北京时间次日早晨 <b>07:10</b>。Actions 排队队列通常有 1~10 分钟的正向浮动。
</details>

---

## ⚖️ 免责声明

1. 本项目仅供 Python 爱好者交流学习网络通信协议分析、JCE/WUP 协议研究与自动化测试用途。
2. 请严格遵守虎牙直播平台的使用协议，严禁用于任何破坏平台正常生态、非法牟利或恶意高频并发行为。
3. 因个人违规使用导致的一切后果由使用者自行承担，与本项目作者无关。

---

## ⭐ Star 支持

如果您觉得本项目好用，欢迎点个右上角的 **⭐ Star** 支持一下！
