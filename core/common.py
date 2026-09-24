#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虎牙每日助手公共基础库 (Huya Helper Common Module)
提供日志输出、敏感信息脱敏、进度条渲染、Cookie 管理、直播间元数据解析与多渠道消息推送。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import sys
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

# 确保 Windows 终端标准输出编码正常
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 默认主播兜底元数据 (未指定直播间时的通用占位)
DEFAULT_ROOM_METADATA = {
    "lp": 0,
    "gid": 0,
    "profileRoom": "未知",
    "nick": "目标主播",
}


def log(module: str, level: str, message: str) -> None:
    """标准格式日志打印输出."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_str = f"[{now}] [{module}] [{level}] {message}"
    try:
        print(full_str, flush=True)
    except UnicodeEncodeError:
        safe_str = full_str.encode("ascii", "ignore").decode("ascii")
        print(safe_str, flush=True)


def mask_account(account: str) -> str:
    """对账号进行脱敏保护处理，用于 Actions 或控制台日志安全输出."""
    if not account:
        return "未设置"
    acc_str = str(account).strip()
    if len(acc_str) >= 7:
        return f"{acc_str[:3]}****{acc_str[-4:]}"
    elif len(acc_str) > 2:
        return f"{acc_str[0]}***{acc_str[-1]}"
    return "***"


def make_progress_bar(current: int, total: int, length: int = 8) -> Tuple[str, str]:
    """生成简约黑白方块进度条 [■■■■■□□□] 及百分比字符串 (专为手机端零折行设计)."""
    if total <= 0:
        return "□" * length, "0.0%"
    ratio = min(max(current / total, 0.0), 1.0)
    filled = int(ratio * length)
    if ratio > 0 and filled == 0:
        filled = 1
    if ratio < 1.0 and filled == length:
        filled = length - 1
    empty = length - filled
    percent_str = f"{ratio * 100:.1f}%"
    bar_str = "■" * filled + "□" * empty
    return bar_str, percent_str


def clean_daka_summary(detail: str, success: bool) -> str:
    """精简打卡状态文字，适配移动端单行不折行."""
    if not detail or "跳过" in detail:
        return "跳过打卡"
    if any(k in detail for k in ("无需重复", "已完成", "已打卡", "已签")):
        return "打卡成功 (+5)"
    if success or "成功" in detail:
        m = re.search(r"\+(\d+)", detail)
        pt = m.group(1) if m else "5"
        return f"打卡成功 (+{pt})"
    return detail[:8] if detail else "打卡异常"


def clean_welfare_summary(detail: str, success: bool) -> str:
    """精简福利状态文字，适配移动端单行不折行."""
    if not detail or "跳过" in detail:
        return "跳过福利"
    if any(k in detail for k in ("已领", "已领取", "成功")) or success:
        return "已领 10 虎粮"
    if "905" in detail:
        return "受App保护(905)"
    return detail[:8] if detail else "暂不可领"


def clean_gift_summary(detail: str, success: bool) -> str:
    """精简送礼状态文字，适配移动端单行不折行."""
    if not detail or "跳过" in detail or "未赠送" in detail:
        return "未赠送"
    if "暂无" in detail or ("0" in detail and ("库存" in detail or "余粮" in detail)):
        return "无余粮跳过"
    if "成功送出" in detail or success:
        m = re.search(r"送出\s*(\d+)", detail)
        cnt = m.group(1) if m else "1"
        return f"成功送出 {cnt} 个"
    return detail[:8] if detail else "赠送异常"


def parse_cookie(cookie_text: str) -> Dict[str, str]:
    """解析 Cookie 字符串为键值字典."""
    cookies: Dict[str, str] = {}
    for part in cookie_text.split(";"):
        name, separator, value = part.strip().partition("=")
        if separator and name:
            cookies[name] = value
    return cookies


def load_cookie_from_files(cookie_file: str = "huya_cookie.txt") -> str:
    """从本地文件尝试加载已保存的 Cookie 字符串."""
    if cookie_file and os.path.exists(cookie_file):
        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                c = f.read().strip()
                if c:
                    return c
        except Exception:
            pass

    if os.path.exists("huya_cookies.json"):
        try:
            with open("huya_cookies.json", "r", encoding="utf-8") as f:
                cookies_list = json.load(f)
                return "; ".join([
                    f"{c['name']}={c['value']}"
                    for c in cookies_list
                    if "huya.com" in c.get("domain", "")
                ])
        except Exception:
            pass
    return ""


def save_cookie_to_files(cookie_text: str, cookie_file: str = "huya_cookie.txt") -> None:
    """将 Cookie 文本安全保存至本地文件."""
    if not cookie_text:
        return
    try:
        with open(cookie_file, "w", encoding="utf-8") as f:
            f.write(cookie_text.strip())
    except Exception as e:
        log("Common", "WARN", f"保存 Cookie 至本地失败: {e}")


def fetch_room_metadata_http(room_url: str) -> Dict[str, Any]:
    """通过 HTTP 请求轻量抓取主播基础元数据 (lp, gid, profileRoom, nick)."""
    info = {
        "lp": DEFAULT_ROOM_METADATA["lp"],
        "gid": DEFAULT_ROOM_METADATA["gid"],
        "profileRoom": DEFAULT_ROOM_METADATA["profileRoom"],
        "nick": DEFAULT_ROOM_METADATA["nick"],
    }
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        req = urllib.request.Request(room_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        m_lp = re.search(r'"lp"\s*:\s*"?(\d+)"?', content)
        m_gid = re.search(r'"gid"\s*:\s*"?(\d+)"?', content)
        m_nick = re.search(r'"nick"\s*:\s*"([^"]+)"', content)
        m_room = re.search(r'"profileRoom"\s*:\s*"?(\d+)"?', content)

        if m_lp:
            info["lp"] = int(m_lp.group(1))
        if m_gid:
            info["gid"] = int(m_gid.group(1))
        if m_nick:
            info["nick"] = m_nick.group(1)
        if m_room:
            info["profileRoom"] = m_room.group(1)
    except Exception as e:
        log("Common", "WARN", f"拉取直播间元数据异常，采用默认值: {e}")

    return info


def build_report_text(summary: Dict[str, Any]) -> str:
    """构造优雅紧凑的黑白方块文本报告 (专为手机端零折行排版优化)."""
    nick = summary.get("nick") or "目标主播"
    clean_nick = re.sub(r"-\d+$", "", nick)
    room_id = summary.get("room_id") or "未知"
    account = summary.get("account", "").strip()
    acc_display = account or "未设置"

    all_success = summary.get("all_success", False)
    status_str = "✅ 完成" if all_success else "ℹ️ 部分完成"

    # 粉丝勋章与等级
    fans_level = summary.get("fans_level", "").strip()
    badge_name = summary.get("badge_name", "").strip()
    if fans_level:
        lvl_num = re.sub(r"\D", "", fans_level)
        level_str = f"Lv.{lvl_num}" if lvl_num else fans_level
    else:
        level_str = "暂无"
    badge_display = f"{level_str} ({badge_name})" if badge_name else level_str

    # 亲密度进度与黑白方块进度条
    current_score = summary.get("current_score")
    next_score = summary.get("next_score")
    intimacy_prog = summary.get("intimacy_progress", "")
    if (current_score is None or next_score is None) and intimacy_prog:
        m = re.search(r"(\d+)\s*/\s*(\d+)", intimacy_prog)
        if m:
            current_score = int(m.group(1))
            next_score = int(m.group(2))

    need_intimacy = summary.get("need_intimacy", "")

    lines = [
        "【🐯 虎牙助手 · 运行报告】",
        "──────────────",
        f"🚩 {clean_nick} ({room_id})",
        f"📱 {acc_display} ｜ {status_str}",
        "",
        f"🏅 勋章：{badge_display}",
    ]

    if current_score is not None and next_score is not None and next_score > 0:
        bar_str, percent_str = make_progress_bar(current_score, next_score, length=8)
        lines.append(f"📊 [{bar_str}] {percent_str}")
        lines.append(f"📈 经验：{current_score} / {next_score}")
    elif need_intimacy and str(need_intimacy) != "未知":
        lines.append(f"📈 经验：升级还需 {need_intimacy}")

    if need_intimacy and str(need_intimacy) != "未知":
        lines.append(f"⏳ 升级：还差 {need_intimacy} 亲密度")

    today_score = summary.get("today_score", "")
    today_quota = summary.get("today_quota", "")
    if today_score:
        quota_str = f" / {today_quota}" if today_quota else ""
        lines.append(f"🔥 今日：{today_score}{quota_str}")

    # 今日执行明细
    details = []
    daka_raw = summary.get("daka_detail", "未执行")
    details.append(("签到", clean_daka_summary(daka_raw, summary.get("daka_success", False))))

    welfare_raw = summary.get("welfare_detail")
    if welfare_raw and welfare_raw != "跳过福利":
        details.append(("福利", clean_welfare_summary(welfare_raw, summary.get("welfare_success", False))))

    gift_raw = summary.get("gift_detail", "未执行")
    details.append(("送礼", clean_gift_summary(gift_raw, summary.get("gift_success", False))))

    left_count = summary.get("left_count")
    if left_count is not None:
        details.append(("余量", f"{left_count} 个"))

    lines.append("")
    lines.append("📋 执行明细：")
    for i, (k, v) in enumerate(details):
        prefix = "└ " if i == len(details) - 1 else "├ "
        lines.append(f"{prefix}{k}：{v}")

    lines.append("──────────────")
    return "\n".join(lines)


def write_github_summary(title: str, text_content: str) -> None:
    """在 GitHub Actions 运行环境中自动写入 Job Summary."""
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file and os.path.exists(os.path.dirname(summary_file)):
        try:
            markdown = f"### {title}\n\n```text\n{text_content}\n```\n"
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write(markdown)
        except Exception:
            pass


def push_wecom_message(summary: Dict[str, Any], config: Dict[str, Any]) -> None:
    """统一向企业微信群机器人 Webhook 及 Actions Summary 推送执行报告."""
    text_content = build_report_text(summary)

    # 1. 写入 GitHub Actions 页面报告
    write_github_summary("虎牙每日助手 · 执行报告", text_content)

    ctx = ssl.create_default_context()

    # 2. 企业微信 Webhook 机器人推送
    webhook_url = config.get("WX_WEBHOOK")
    if webhook_url:
        try:
            log("Common", "INFO", "正在通过企业微信群机器人 Webhook 推送全文本报告...")
            payload = {
                "msgtype": "text",
                "text": {"content": text_content},
            }
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                if res_data.get("errcode") == 0:
                    log("Common", "SUCCESS", "企业微信 Webhook 纯文本消息推送成功！")
                else:
                    log("Common", "WARN", f"企业微信 Webhook 推送返回: {res_data}")
        except Exception as e:
            log("Common", "ERROR", f"企业微信 Webhook 推送失败: {e}")
