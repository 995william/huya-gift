#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""虎牙看广告领虎粮的人工辅助脚本。

本脚本只查询广告任务状态和虎粮包裹库存。广告必须由用户在虎牙 App
中手动完整观看；脚本不会模拟广告播放，也不会提交广告完成或奖励回调。
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Callable

from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.mobile_bot import PackageGiftClient, PackageInventory, load_cookie_from_files
from core.wup import HuyaWupClient, JceInputStream, JceOutputStream


DEFAULT_PID = 0
PACKAGE_TAB_ID = -10000
AD_TIGER_FOOD_BIZ_TYPE = 1


@dataclass(frozen=True)
class AdTigerFoodStatus:
    """看广告领虎粮入口的只读状态。"""

    signal_code: str
    found: bool
    name: str = ""
    button_text: str = ""
    display_type: int = 0
    reward_count: int = 0
    remaining_seconds: int = 0
    status_code: int = 0
    status_text: str = ""
    finish_text: str = ""
    show_remaining_time: bool = False
    bubble_text: str = ""
    button_disabled: bool = True

    @property
    def available(self) -> bool:
        return (
            self.signal_code == "0"
            and self.found
            and self.display_type == 1
            and self.status_code > 0
            and not self.button_disabled
        )


class AdTigerFoodTaskClient(HuyaWupClient):
    """只读查询 App 包裹页的看广告领虎粮入口。"""

    def query(self, pid: int) -> AdTigerFoodStatus:
        if pid <= 0:
            raise ValueError("主播 PID 必须为正整数")

        out = JceOutputStream()
        out.write_struct_begin(0)
        self._write_user_id(out, 0)
        out.write_long(pid, 1)
        out.write_int(PACKAGE_TAB_ID, 2)
        out.write_struct_end()

        root, response = self._send_wup(
            "wupui", "getPropsListPlacement", out.get_bytes()
        )
        signal_code = self._signal_code(root)
        placements = self._placements(response)

        for placement in placements:
            if not isinstance(placement, dict):
                continue
            if placement.get(7) == AD_TIGER_FOOD_BIZ_TYPE:
                return self._parse_status(signal_code, placement)

        return AdTigerFoodStatus(signal_code=signal_code, found=False)

    def _write_user_id(self, out: JceOutputStream, tag: int) -> None:
        out.write_struct_begin(tag)
        out.buf.write(self.user_id_bytes[1:-1])
        out.write_struct_end()

    @staticmethod
    def _placements(response: dict) -> list:
        wrapper = response.get("tRsp", {})
        payload = wrapper.get(0, {}) if isinstance(wrapper, dict) else {}
        placements = payload.get(0, []) if isinstance(payload, dict) else []
        return placements if isinstance(placements, list) else []

    @staticmethod
    def _parse_status(signal_code: str, placement: dict) -> AdTigerFoodStatus:
        raw_data = placement.get(8, b"")
        ad_info = (
            JceInputStream(raw_data).parse_all()
            if isinstance(raw_data, (bytes, bytearray))
            else {}
        )
        return AdTigerFoodStatus(
            signal_code=signal_code,
            found=True,
            name=str(placement.get(1, "")),
            button_text=str(placement.get(3, "")),
            display_type=int(placement.get(6, 0)),
            reward_count=int(ad_info.get(0, 0)),
            remaining_seconds=int(ad_info.get(1, 0)),
            status_code=int(ad_info.get(2, 0)),
            finish_text=str(ad_info.get(3, "")),
            status_text=str(ad_info.get(5, "")),
            show_remaining_time=ad_info.get(6, 0) == 1,
            bubble_text=str(ad_info.get(8, "")),
            button_disabled=ad_info.get(9, 1) != 0,
        )


def query_inventory(client: PackageGiftClient, pid: int) -> PackageInventory:
    inventory = client.query_tiger_food(pid)
    if inventory.signal_code != "0":
        raise RuntimeError(
            f"虎粮库存查询失败（协议码 {inventory.signal_code or '缺失'}）"
        )
    return inventory


def wait_for_inventory_increase(
    client: PackageGiftClient,
    pid: int,
    before_count: int,
    timeout: float,
    poll_interval: float,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> PackageInventory:
    """等待包裹库存增加，超时后返回最后一次查询结果。"""

    deadline = monotonic() + timeout
    latest = query_inventory(client, pid)
    while latest.count <= before_count and monotonic() < deadline:
        sleep(min(poll_interval, max(0.0, deadline - monotonic())))
        latest = query_inventory(client, pid)
    return latest


def format_duration(seconds: int) -> str:
    minutes, second = divmod(max(0, seconds), 60)
    hour, minute = divmod(minutes, 60)
    if hour:
        return f"{hour}小时{minute}分{second}秒"
    if minute:
        return f"{minute}分{second}秒"
    return f"{second}秒"


def print_task_status(status: AdTigerFoodStatus) -> None:
    if status.signal_code != "0":
        print(f"广告任务查询失败：协议码 {status.signal_code or '缺失'}")
        return
    if not status.found:
        print("当前包裹页没有返回看广告领虎粮入口。")
        return

    availability = "可使用" if status.available else "暂不可使用"
    print(f"任务：{status.name or '虎粮礼包'}（{availability}）")
    print(f"单次奖励：{status.reward_count} 虎粮")
    if status.status_text:
        print(f"状态说明：{status.status_text}")
    if status.button_text:
        print(f"App 按钮：{status.button_text}")
    if status.show_remaining_time and status.remaining_seconds > 0:
        print(f"剩余时间：{format_duration(status.remaining_seconds)}")
    if not status.available and status.finish_text:
        print(f"提示：{status.finish_text}")


def run_guided_rounds(
    task_client: AdTigerFoodTaskClient,
    package_client: PackageGiftClient,
    pid: int,
    rounds: int,
    verify_timeout: float,
    poll_interval: float,
) -> int:
    completed = 0
    for round_number in range(1, rounds + 1):
        status = task_client.query(pid)
        print(f"\n=== 第 {round_number}/{rounds} 轮 ===")
        print_task_status(status)
        if not status.available:
            print("当前不能开始下一轮，请稍后在 App 中确认入口状态。")
            return 0 if completed else 2

        before = query_inventory(package_client, pid)
        print(f"观看前包裹虎粮：{before.count}")
        print("请在虎牙 App 中点击对应按钮并完整观看广告。")
        print("本脚本不会打开或模拟广告，也不会提交奖励完成回调。")
        answer = input("观看完成后按回车验证库存，输入 q 退出：")
        if answer.lower() == "q":
            print("已退出，未执行任何奖励请求。")
            return 0

        after = wait_for_inventory_increase(
            package_client,
            pid,
            before.count,
            verify_timeout,
            poll_interval,
        )
        gained = after.count - before.count
        if gained <= 0:
            print(
                f"未在 {format_duration(int(verify_timeout))} 内确认库存增加，"
                f"当前仍为 {after.count}。"
            )
            return 2

        completed += 1
        print(f"验证成功：本轮实际增加 {gained} 虎粮，当前库存 {after.count}。")
        if status.reward_count > 0 and gained != status.reward_count:
            print(
                f"注意：任务显示奖励 {status.reward_count}，"
                f"实际库存变化为 {gained}。"
            )

    print(f"\n已完成并验证 {completed} 轮。")
    return 0


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("不能小于 0")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="人工观看虎牙 App 广告，并通过 WUP 库存查询验证虎粮到账"
    )
    parser.add_argument("--pid", type=positive_int, default=DEFAULT_PID, help="主播 PID")
    parser.add_argument(
        "--cookie-file",
        default="huya_cookie.txt",
        help="本地 Cookie 文件；HUYA_COOKIE 环境变量优先",
    )
    parser.add_argument(
        "--rounds",
        type=positive_int,
        default=1,
        help="人工观看轮数，每轮都需要按回车确认（默认 1）",
    )
    parser.add_argument(
        "--verify-timeout",
        type=non_negative_float,
        default=60.0,
        help="观看后等待库存更新的秒数（默认 60）",
    )
    parser.add_argument(
        "--poll-interval",
        type=positive_int,
        default=3,
        help="库存轮询间隔秒数（默认 3）",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="只查询任务状态和当前库存，不进入人工观看流程",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cookie = os.getenv("HUYA_COOKIE", "") or load_cookie_from_files(args.cookie_file)
    if not cookie:
        print("未找到 Cookie，请设置 HUYA_COOKIE 或准备 huya_cookie.txt。")
        return 1

    try:
        task_client = AdTigerFoodTaskClient(cookie)
        package_client = PackageGiftClient(cookie)
        if args.status_only:
            status = task_client.query(args.pid)
            inventory = query_inventory(package_client, args.pid)
            print_task_status(status)
            print(f"当前包裹虎粮：{inventory.count}")
            return 0 if status.signal_code == "0" else 1
        return run_guided_rounds(
            task_client,
            package_client,
            args.pid,
            args.rounds,
            args.verify_timeout,
            float(args.poll_interval),
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"执行失败：{error}")
        return 1
    except KeyboardInterrupt:
        print("\n已由用户中止。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
