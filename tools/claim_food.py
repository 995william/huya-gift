#!/usr/bin/env python3
"""独立查询或领取粉丝团每日 10 虎粮。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.mobile_bot import DailyTigerFoodClient, WelfareStatus


DEFAULT_PID = 0
EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_PROTOCOL = 3
EXIT_NOT_ELIGIBLE = 4
EXIT_CLAIM_FAILED = 5


def load_cookie(cookie_file: Path) -> str:
    env_cookie = os.getenv("HUYA_COOKIE", "").strip()
    if env_cookie:
        return env_cookie
    try:
        cookie = cookie_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"无法读取 Cookie 文件 {cookie_file}: {exc}") from exc
    if not cookie:
        raise ValueError(f"Cookie 文件为空：{cookie_file}")
    return cookie


def validate_status(status: WelfareStatus) -> None:
    if status.signal_code != "0":
        raise RuntimeError(f"查询被协议网关拒绝（状态码 {status.signal_code or '缺失'}）")
    if status.business_code != 0:
        raise RuntimeError(f"查询业务返回异常（状态码 {status.business_code}）")


def claim_daily_food(client: DailyTigerFoodClient, pid: int, dry_run: bool) -> int:
    before = client.query_welfare(pid)
    validate_status(before)
    print(f"领取前状态：{before.state}（{before.description}）")

    if before.state == 4:
        print("今日 10 虎粮已经领取，无需重复请求。")
        return EXIT_OK
    if before.state != 3:
        print(f"当前不可领取：{before.description}")
        return EXIT_NOT_ELIGIBLE
    if dry_run:
        print("dry-run：当前可领取，未发送领取请求。")
        return EXIT_OK

    claim = client.claim_welfare(pid)
    if claim.signal_code != "0":
        detail = f"，{claim.signal_description}" if claim.signal_description else ""
        print(f"领取请求失败：协议状态码 {claim.signal_code or '缺失'}{detail}")
        return EXIT_CLAIM_FAILED
    if claim.business_code not in (None, 0):
        print(f"领取请求失败：业务状态码 {claim.business_code}")
        return EXIT_CLAIM_FAILED

    after = None
    for attempt in range(3):
        if attempt:
            time.sleep(0.5)
        after = client.query_welfare(pid)
        validate_status(after)
        if after.state == 4:
            break

    assert after is not None
    print(f"领取后状态：{after.state}（{after.description}）")
    if after.state != 4:
        print("领取响应未被状态查询确认，不能判定为成功。")
        return EXIT_CLAIM_FAILED

    print(f"领取成功：虎粮 x{claim.item_count or 10}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="纯 WUP 协议领取粉丝团每日 10 虎粮")
    parser.add_argument("--pid", type=int, default=int(os.getenv("HUYA_PID", DEFAULT_PID)))
    parser.add_argument(
        "--cookie-file",
        type=Path,
        default=Path(os.getenv("HUYA_COOKIE_FILE", "huya_cookie.txt")),
        help="Cookie 文件路径；HUYA_COOKIE 环境变量优先",
    )
    parser.add_argument("--dry-run", action="store_true", help="只查询，不领取")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.pid <= 0:
        print("配置错误：pid 必须是正整数", file=sys.stderr)
        return EXIT_CONFIG
    try:
        return claim_daily_food(
            DailyTigerFoodClient(load_cookie(args.cookie_file)), args.pid, args.dry_run
        )
    except ValueError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return EXIT_CONFIG
    except Exception as exc:
        print(f"协议请求异常：{exc}", file=sys.stderr)
        return EXIT_PROTOCOL


if __name__ == "__main__":
    raise SystemExit(main())
