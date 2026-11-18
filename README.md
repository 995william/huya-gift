<div align="center">

# 虎牙每日自动助手 (Huya Daily Helper)

**纯 WUP/JCE 协议全自动打卡 · 粉丝团专属福利领取 · 智能赠送包裹虎粮 · 集中管控中枢联动 · 内置 UDB 扫码续签**

[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/995william/huya-gift/checkin.yml?branch=main&label=%E7%AD%BE%E5%88%B0%E6%B5%81%E6%B0%B4%E7%BA%BF&logo=github)](https://github.com/995william/huya-gift/actions)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 📖 项目简介

本项目是专为**虎牙直播（Huya.com）**打造的自动化助手工具，实现每日自动完成粉丝团打卡（亲密度 +5）、移动端专属福利领取（每日 10 虎粮）、包裹免费虎粮库存查询及定向赠送给指定主播，并生成移动端零折行的 8 格黑白方块进度报告。

现已全面接入 **William 签到与自动化管控中枢（[https://checkin.wwcoder.top](https://checkin.wwcoder.top)）**，提供集中调度、亲密度数据归档、每日早报聚合推送，以及**原生内置虎牙官方 UDB 扫码免密续签中心**。

项目提供两种运行引擎：
- ⚡ **v2（推荐 · 移动端纯协议版）**：采用纯 Python 原生实现的 JCE/WUP 二进制协议直连官方网关（`wup.huya.com`），秒级完成状态校验、打卡与领粮送礼，无需启动无头浏览器。
- 🌐 **v1（网页端兜底版）**：基于 Playwright 自动化驱动无头 Chromium 模拟真实交互。

---

## 🌐 集中管控中枢与内置扫码续签

本项目由 **[https://checkin.wwcoder.top](https://checkin.wwcoder.top)** 统一纳管（项目标识：`huya`）：

1. **统一标准入口（`checkin.yml`）**：统一通过 `.github/workflows/checkin.yml`（`workflow_dispatch`）接收中枢每日定时调度或手动参数化运行，彻底告别 GitHub 原生 `schedule` 队列延迟与冗余保活提交。
2. **原生 UDB 扫码直写 Secret（零明文暴露）**：
   - 打开管控台 **[https://checkin.wwcoder.top](https://checkin.wwcoder.top)** 进入「虎牙每日助手」续签面板；
   - 使用手机 **虎牙直播 App 扫一扫** 确认授权；
   - 中枢直接从官方 UDB 通道提取全量核心协议凭据（`yyuid`、`udb_biztoken`、`udb_passdata` 等），通过公钥加密直接写入本仓库 `HUYA_COOKIE` Secret 并触发验证任务，**无需任何中转 `update_cookie.yml` 明文传参**。
3. **标准化上报与托管静默（`hub_reporter.py`）**：
   - 每次执行完毕后自动上报打卡状态、粉丝勋章等级、今日亲密度增量、赠送虎粮个数及脱敏报告卡片；
   - 当 `HUB_MANAGED_NOTIFY="true"` 时，全部成功默认静默单仓企微直推（交由中枢每日早报统一推送），异常失败或手动指定 `wechat_push="true"` 时立即发送单仓报告。

---

## 📱 消息卡片预览（手机端零折行排版）

```text
【🐯 虎牙助手 · 运行报告】
──────────────
🚩 演示主播 (123456)
📱 138****0000 ｜ ✅ 完成

🏅 勋章：Lv.22 (徽章)
📊 [■■■■■■■□] 95.9%
📈 经验：167817 / 175000
⏳ 升级：还差 7183 亲密度
🔥 今日：15 / 4000

📋 执行明细：
├ 签到：打卡成功 (+5)
├ 福利：已领 10 虎粮
├ 送礼：已送 10 个
└ 余量：0 个
──────────────
```

---

## 🚀 GitHub Actions Secrets 与 Variables 配置

在仓库 **Settings -> Secrets and variables -> Actions** 中支持配置：

### 1. Repository Secrets

| Secret 变量名 | 必填 | 说明 |
| :--- | :---: | :--- |
| `HUYA_COOKIE` | **是** | 虎牙完整登录 Cookie（推荐在 `checkin.wwcoder.top` 扫码一键自动同步） |
| `HUYA_ROOM_URL` | **是** | 目标主播直播间地址（如 `https://www.huya.com/123456`，亦可配在 Variables） |
| `CHECKIN_HUB_TOKEN` | 推荐 | 集中管控中枢上报鉴权令牌 |
| `WX_WEBHOOK` | 可选 | 企业微信群机器人 Webhook 地址 |

### 2. Repository Variables（可选覆盖）

| Variable 变量名 | 默认值 | 说明 |
| :--- | :---: | :--- |
| `HUYA_VERSION` | `v2` | 运行版本（`v2` 移动端纯协议版推荐，`v1` 网页端） |
| `HUYA_GIFT_COUNT` | `0` | 每次赠送虎粮数量（`0` 表示全部赠送） |
| `HUYA_DAKA` | `true` | 是否执行每日粉丝团打卡（亲密度 +5） |
| `HUYA_WELFARE` | `true` | 是否领取移动端每日专属 10 虎粮 |
| `HUYA_WECHAT_PUSH` | `auto` | `auto` 跟随中枢托管策略，`true` 强制开启，`false` 禁用 |

---

## 💻 本地调试与辅助工具

```bash
git clone https://github.com/995william/huya-gift.git
cd huya-gift
pip install -r requirements.txt

# 本地运行 v2 移动端纯协议版
python main.py --version v2 --room https://www.huya.com/123456 --count 0

# 本地浏览器扫码提取 Cookie（离线备用方式）
python tools/get_cookie.py
```

---

## 📂 项目目录结构

```text
huya-gift/
├── .github/
│   └── workflows/
│       └── checkin.yml              # 统一受控调度工作流（workflow_dispatch）
├── core/                            # 核心业务与协议引擎
│   ├── common.py                    # 公共基础库（脱敏、进度条、房间解析与托管推送）
│   ├── wup.py                       # WUP/JCE 二进制编解码器与网关驱动
│   ├── mobile_bot.py                # v2 移动端纯协议打卡、领粮、送粮实现
│   └── web_bot.py                   # v1 网页端 Playwright 浏览器自动化实现
├── tools/                           # 本地辅助工具脚本
│   ├── get_cookie.py                # 本地浏览器提取 Cookie 离线工具
│   ├── claim_food.py                # 独立查询/领取每日 10 虎粮工具
│   └── ad_helper.py                 # 广告领虎粮库存核对工具
├── tests/
│   └── test_report.py               # 报表渲染与协议解析单元测试
├── main.py                          # 统一命令行主入口与中枢数据同步器
├── hub_reporter.py                  # 集中管控中枢零依赖标准化上报 SDK
├── .env.example                     # 环境变量脱敏模板
├── requirements.txt                 # 项目依赖
└── README.md                        # 项目架构与使用指南
```

---

## ⚖️ 免责声明

本项目仅供 Python 协议学习与个人效率自动化研究使用，请严格遵守虎牙直播平台使用协议，严禁用于任何违规或商业用途。
