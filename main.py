#!/usr/bin/env python3
"""虎牙每日助手统一入口（支持集中管控中枢标准化上报与托管推送）。"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

from core.common import (
    build_report_text,
    clean_daka_summary,
    clean_gift_summary,
    clean_welfare_summary,
    mask_account,
)
from hub_reporter import report_to_hub


TRUE_VALUES = {"1", "true", "yes", "on", "auto"}
FALSE_VALUES = {"0", "false", "no", "off"}


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{name} 必须是 true/false/auto、1/0、yes/no 或 on/off")


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc


# ==================== 统一配置区 ====================
# 直接修改这里即可改变本地默认行为。敏感值建议保持为空，由环境变量或
# GitHub Actions Secrets 注入，避免提交到仓库。
USER_CONFIG = {
    "version": "v2",  # 启用版本：v1 网页端，v2 移动端协议版
    "count": 0,  # 每次赠送虎粮数量；0 表示送出包裹内全部虎粮
    "room": "",  # 目标主播直播间地址；建议通过环境变量 HUYA_ROOM_URL 或 --room 传入
    "do_daka": True,  # 是否执行每日粉丝团打卡
    "do_welfare": True,  # 是否领取移动端每日 10 虎粮
    "wechat_push": True,  # 是否推送企业微信执行报告
    "local_debug": False,  # True 显示浏览器窗口，False 使用无头模式
    "account": "",  # 虎牙账号；建议通过 HUYA_ACCOUNT Secret 注入
    "password": "",  # 虎牙密码；建议通过 HUYA_PASSWORD Secret 注入
    "cookie": "",  # 虎牙 Cookie；建议通过 HUYA_COOKIE Secret 注入
    "cookie_file": "huya_cookie.txt",  # 本地 Cookie 文件路径
    "wx_webhook": "",  # 企业微信群机器人 Webhook；建议通过 Secret 注入
}


@dataclass(frozen=True)
class AppConfig:
    version: str
    count: int
    room: str
    do_daka: bool
    do_welfare: bool
    wechat_push: bool
    force_wechat_push: bool
    local_debug: bool
    account: str
    password: str
    cookie: str
    cookie_file: str
    wx_webhook: str


def load_runtime_config() -> dict:
    """用环境变量覆盖 USER_CONFIG，供 GitHub Actions 和本地环境使用。"""
    raw_push_env = (os.getenv("HUYA_WECHAT_PUSH") or "").strip().lower()
    raw_force_env = (os.getenv("HUYA_FORCE_WECHAT_PUSH") or "").strip().lower()
    # 当用户显式在环境变量传入 HUYA_FORCE_WECHAT_PUSH=true 时强制开启单仓直推
    force_push = raw_force_env in {"1", "true", "yes", "on"}
    # 若未处于中枢托管模式且 HUYA_WECHAT_PUSH=true，默认本来就会直推
    if os.getenv("HUB_MANAGED_NOTIFY", "").strip().lower() != "true" and raw_push_env in {"1", "true", "yes", "on"}:
        force_push = True

    return {
        "version": os.getenv("HUYA_VERSION", USER_CONFIG["version"]).lower(),
        "count": env_int("HUYA_GIFT_COUNT", USER_CONFIG["count"]),
        "room": os.getenv("HUYA_ROOM_URL", USER_CONFIG["room"]),
        "do_daka": env_bool("HUYA_DAKA", USER_CONFIG["do_daka"]),
        "do_welfare": env_bool("HUYA_WELFARE", USER_CONFIG["do_welfare"]),
        "wechat_push": env_bool("HUYA_WECHAT_PUSH", USER_CONFIG["wechat_push"]),
        "force_wechat_push": force_push,
        "local_debug": env_bool("HUYA_LOCAL_DEBUG", USER_CONFIG["local_debug"]),
        "account": os.getenv("HUYA_ACCOUNT", USER_CONFIG["account"]),
        "password": os.getenv("HUYA_PASSWORD", USER_CONFIG["password"]),
        "cookie": os.getenv("HUYA_COOKIE", USER_CONFIG["cookie"]),
        "cookie_file": os.getenv("HUYA_COOKIE_FILE", USER_CONFIG["cookie_file"]),
        "wx_webhook": os.getenv("WX_WEBHOOK", USER_CONFIG["wx_webhook"]),
    }


def build_parser(defaults: dict) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="虎牙每日助手统一调度器")
    parser.add_argument(
        "-v", "--version", choices=("v1", "v2"), default=defaults["version"],
        help="运行版本：v1 网页端，v2 移动端协议版",
    )
    parser.add_argument(
        "-c", "--count", type=int, default=defaults["count"],
        help="赠送虎粮数量；0 表示送出全部库存",
    )
    parser.add_argument("--room", default=defaults["room"], help="目标直播间地址")

    daka = parser.add_mutually_exclusive_group()
    daka.add_argument("--daka", dest="do_daka", action="store_true", help="执行每日打卡")
    daka.add_argument("--no-daka", dest="do_daka", action="store_false", help="跳过每日打卡")

    welfare = parser.add_mutually_exclusive_group()
    welfare.add_argument("--welfare", dest="do_welfare", action="store_true", help="领取每日 10 虎粮（仅 v2）")
    welfare.add_argument("--no-welfare", dest="do_welfare", action="store_false", help="跳过每日 10 虎粮领取")

    push = parser.add_mutually_exclusive_group()
    push.add_argument("--wechat-push", dest="wechat_push", action="store_true", help="启用企业微信推送")
    push.add_argument("--no-wechat-push", dest="wechat_push", action="store_false", help="禁用企业微信推送")

    debug = parser.add_mutually_exclusive_group()
    debug.add_argument(
        "--local-debug", "--headful", dest="local_debug", action="store_true",
        help="本地调试模式：显示浏览器窗口（仅 v1）",
    )
    debug.add_argument(
        "--no-local-debug",
        dest="local_debug",
        action="store_false",
        help="后台无头模式（仅 v1）",
    )

    parser.set_defaults(
        do_daka=defaults["do_daka"],
        do_welfare=defaults["do_welfare"],
        wechat_push=defaults["wechat_push"],
        local_debug=defaults["local_debug"],
    )
    return parser


def load_config(argv: list[str] | None = None) -> AppConfig:
    defaults = load_runtime_config()
    if defaults["version"] not in ("v1", "v2"):
        raise ValueError("HUYA_VERSION 必须是 v1 或 v2")

    effective_argv = argv if argv is not None else sys.argv[1:]
    cli_forced_push = "--wechat-push" in effective_argv

    args = build_parser(defaults).parse_args(argv)
    if args.count < 0:
        raise ValueError("赠送虎粮数量不能小于 0")
    if not args.room:
        raise ValueError("直播间地址不能为空")

    secure_config = {
        key: defaults[key]
        for key in (
            "account", "password", "cookie", "cookie_file", "wx_webhook",
        )
    }
    return AppConfig(
        version=args.version,
        count=args.count,
        room=args.room,
        do_daka=args.do_daka,
        do_welfare=args.do_welfare,
        wechat_push=args.wechat_push,
        force_wechat_push=bool(defaults["force_wechat_push"] or cli_forced_push),
        local_debug=args.local_debug,
        **secure_config,
    )


def sync_summary_to_hub(summary: Dict[str, Any], duration_ms: int) -> None:
    """提取虎牙执行摘要、亲密度与虎粮赠送状态，上报至集中管控中枢."""
    nick = summary.get("nick") or "目标主播"
    clean_nick = re.sub(r"-\d+$", "", str(nick))
    masked_acc = mask_account(summary.get("account", "")) if summary.get("account") else "默认账号"

    all_ok = bool(summary.get("all_success", False))
    daka_ok = bool(summary.get("daka_success", False))
    gift_ok = bool(summary.get("gift_success", False))
    daka_detail = str(summary.get("daka_detail", ""))
    welfare_detail = str(summary.get("welfare_detail", ""))
    gift_detail = str(summary.get("gift_detail", ""))

    gift_count = int(summary.get("gift_count") or 0)
    daka_intimacy = int(summary.get("daka_intimacy") or 0)

    if "登录失败" in daka_detail or (not daka_ok and not gift_ok):
        hub_status = "failed"
    elif all_ok:
        if any(k in daka_detail for k in ("无需重复", "已完成", "已打卡", "已签")) and gift_count == 0:
            hub_status = "already_signed"
        else:
            hub_status = "success"
    else:
        hub_status = "partial" if daka_ok else "failed"

    reward_total: float | None = None
    if hub_status != "failed":
        today_raw = str(summary.get("today_score", "")).strip()
        if today_raw.isdigit():
            reward_total = float(int(today_raw))
        else:
            reward_total = float(daka_intimacy + gift_count)

    current_score = summary.get("current_score")
    balance_total: float | None = None
    if isinstance(current_score, (int, float)):
        balance_total = float(current_score)

    fans_level = str(summary.get("fans_level", "")).strip()
    lvl_digits = re.sub(r"\D", "", fans_level)
    lvl_tag = f"Lv.{lvl_digits}" if lvl_digits else ""

    if hub_status in ("success", "already_signed"):
        gain_val = int(reward_total) if reward_total is not None else (daka_intimacy + gift_count)
        gift_tag = f"送{gift_count}粮" if gift_count > 0 else "已打卡"
        asset_text = f"{lvl_tag + ' · ' if lvl_tag else ''}亲密度+{gain_val} ({gift_tag})"
    elif hub_status == "partial":
        asset_text = f"部分完成 (送{gift_count}粮)"
    else:
        asset_text = "登录失败 (需扫码续签)" if "登录失败" in daka_detail else "执行异常"

    if "登录失败" in daka_detail:
        summary_text = f"[{clean_nick}] Cookie 已失效，请前往 checkin.wwcoder.top 扫码续签"
    else:
        daka_s = clean_daka_summary(daka_detail, daka_ok, daka_intimacy)
        gift_s = clean_gift_summary(gift_detail, gift_ok, gift_count)
        parts = [f"签到:{daka_s}"]
        if welfare_detail and welfare_detail != "跳过福利":
            welfare_s = clean_welfare_summary(welfare_detail, bool(summary.get("welfare_success", False)))
            parts.append(f"福利:{welfare_s}")
        parts.append(f"送礼:{gift_s}")
        summary_text = f"[{clean_nick}] " + " | ".join(parts)

    masked_summary_dict = {
        **summary,
        "account": masked_acc,
    }
    raw_card = build_report_text(masked_summary_dict)

    acc_status = hub_status if hub_status != "partial" else ("success" if daka_ok else "failed")
    accounts_payload = [
        {
            "account_mask": masked_acc,
            "status": acc_status,
            "reward_num": reward_total,
            "balance_num": balance_total,
            "unit": "点",
            "message": summary_text,
            "extra": {
                "room_id": str(summary.get("room_id", "")),
                "nick": clean_nick,
                "fans_level": fans_level,
                "badge_name": str(summary.get("badge_name", "")),
                "gift_count": gift_count,
                "left_count": summary.get("left_count"),
            },
        }
    ]

    report_to_hub(
        project_slug="huya",
        status=hub_status,
        summary=summary_text,
        duration_ms=duration_ms,
        asset_text=asset_text,
        reward_total=reward_total,
        balance_total=balance_total,
        raw_card=raw_card,
        accounts=accounts_payload,
    )


def main(argv: list[str] | None = None) -> int:
    start_ts = time.time()
    try:
        config = load_config(argv)
    except ValueError as exc:
        err_text = f"配置错误：{exc}"
        print(err_text, file=sys.stderr)
        report_to_hub(
            project_slug="huya",
            status="failed",
            summary=err_text,
            duration_ms=int((time.time() - start_ts) * 1000),
            asset_text="配置缺失",
            raw_card=err_text,
        )
        return 2

    mode = (
        "本地调试" if config.local_debug else "后台运行"
    ) if config.version == "v1" else "纯 WUP 协议"
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [main] "
        f"版本={config.version}，送粮={config.count}，模式={mode}"
    )

    if config.version == "v1":
        from core import web_bot

        summary = web_bot.run(config)
    else:
        from core import mobile_bot

        summary = mobile_bot.run(config)

    duration_ms = int((time.time() - start_ts) * 1000)
    sync_summary_to_hub(summary, duration_ms)

    return 0 if summary.get("all_success", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
