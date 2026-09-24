#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虎牙每日自动助手 - v2 移动 App 端纯协议版本 (Huya Mobile App Bot v2)
功能特性：
1. 【移动端专属福利（10 虎粮）】：
   - 基于 queryFansGroupTaskInfo 精确探查每日粉丝团福利状态 (可领/已领/计时中)；
   - 基于 operateFansBox 自动领取，并在领取后复查状态，避免把失败响应误判为成功。
2. 【移动端原生 WUP 打卡】：
   - 采用纯 Python JCE 协议直连官方 wup.huya.com 网关 (getFansSign / setFansSign)；
   - 秒级直连完成打卡，亲密度 +5，无需启动浏览器。
3. 【高精度勋章与亲密度提取】：
   - 基于 liveui.queryBadgeInfoList 拉取真实粉丝勋章、粉丝等级、当前亲密度、升级还需亲密度。
4. 【包裹免费虎粮赠送】：
   - 基于 getPackageGift / getSequence / consumeGiftSafe 查询并赠送虎粮；
   - 赠送后再次查询包裹，以真实库存变化确认结果。
5. 【企业微信全文本推送】：
   - 严格采用全文本格式 (msgtype: text)，清晰完整展示等级、亲密度进度、福利与打卡送粮详情。
6. 【完全独立运行】：既可被 main.py 统一调用，也可直接独立运行 `python huya_v2.py`。
"""

import argparse
import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
# 引入公共基础库与官方 WUP 协议核心驱动
from .common import (
    clean_daka_summary,
    clean_gift_summary,
    clean_welfare_summary,
    fetch_room_metadata_http,
    load_cookie_from_files,
    make_progress_bar,
    mask_account,
    parse_cookie,
    push_wecom_message,
)
from .common import log as common_log
from .wup import HuyaWupClient, JceOutputStream


def log(level: str, message: str) -> None:
    common_log("v2-App", level, message)
DEFAULT_CONFIG = {
    "GIFT_COUNT": int(os.getenv("HUYA_GIFT_COUNT", "0").strip() or 0),
    "ROOM_URL": os.getenv("HUYA_ROOM_URL", "").strip(),
    "ACCOUNT": os.getenv("HUYA_ACCOUNT", "").strip(),
    "COOKIE": os.getenv("HUYA_COOKIE", "").strip(),
    "COOKIE_FILE": os.getenv("HUYA_COOKIE_FILE", "huya_cookie.txt").strip(),
    "DO_DAKA": os.getenv("HUYA_DAKA", "true").lower() in ("true", "1", "yes"),
    "DO_WELFARE": os.getenv("HUYA_WELFARE", "true").lower() in ("true", "1", "yes"),
    "WECHAT_PUSH": os.getenv("HUYA_WECHAT_PUSH", "true").lower() in ("true", "1", "yes"),
    "WX_WEBHOOK": os.getenv("WX_WEBHOOK", "").strip(),
}

DEFAULT_ROOM_DEFAULTS = {
    "lp": 0,
    "gid": 0,
    "profileRoom": "未知",
    "nick": "目标主播",
}

DEFAULT_APP_UA = "android&13.4.63&official&35"
DEFAULT_DEVICE_MODEL = "22011211C"
WELFARE_STATE_DESCRIPTIONS = {
    1: "未达到领取条件",
    2: "计时中",
    3: "可领取",
    4: "今日已领取",
}


@dataclass(frozen=True)
class WelfareStatus:
    signal_code: str
    business_code: int
    state: int

    @property
    def description(self) -> str:
        return WELFARE_STATE_DESCRIPTIONS.get(self.state, f"未知状态({self.state})")


@dataclass(frozen=True)
class ClaimResponse:
    signal_code: str
    signal_description: str
    business_code: int | None
    item_count: int


@dataclass(frozen=True)
class PackageInventory:
    signal_code: str
    item_type: int
    item_name: str
    count: int


@dataclass(frozen=True)
class GiftSendResponse:
    signal_code: str
    pay_code: int
    item_type: int
    item_count: int
    message: str



class DailyTigerFoodClient(HuyaWupClient):
    """使用已验证的新版 App UserId 领取每日 10 虎粮。"""

    def __init__(self, cookie_text: str):
        self.cookies = parse_cookie(cookie_text)
        super().__init__(cookie_text)
        uid_text = self.cookies.get("yyuid") or self.cookies.get("udb_uid") or ""
        if not uid_text.isdigit() or int(uid_text) <= 0:
            raise ValueError("Cookie 中缺少有效的 yyuid/udb_uid")
        self.uid = int(uid_text)
        self.user_id_bytes = self._encode_app_user_id()

    def _encode_app_user_id(self) -> bytes:
        token_type_text = os.getenv("HUYA_TOKEN_TYPE", "2").strip() or "2"
        try:
            token_type = int(token_type_text)
        except ValueError as exc:
            raise ValueError("HUYA_TOKEN_TYPE 必须是整数") from exc

        out = JceOutputStream()
        out.write_struct_begin(0)
        out.write_long(self.uid, 0)
        out.write_string(os.getenv("HUYA_APP_GUID", "").strip(), 1)
        out.write_string(os.getenv("HUYA_UDB_TOKEN", "").strip(), 2)
        out.write_string(os.getenv("HUYA_APP_UA", DEFAULT_APP_UA).strip() or DEFAULT_APP_UA, 3)
        out.write_string(self.cookie_str, 4)
        out.write_int(token_type, 5)
        out.write_string(
            os.getenv("HUYA_DEVICE_MODEL", DEFAULT_DEVICE_MODEL).strip()
            or DEFAULT_DEVICE_MODEL,
            6,
        )
        out.write_string(os.getenv("HUYA_QIMEI", "").strip(), 7)
        out.write_struct_end()
        return out.get_bytes()

    def _write_user_id(self, out: JceOutputStream, tag: int) -> None:
        out.write_struct_begin(tag)
        out.buf.write(self.user_id_bytes[1:-1])
        out.write_struct_end()

    @staticmethod
    def _signal_status(root: dict[int, Any]) -> tuple[str, str]:
        status = root.get(10, {})
        if not isinstance(status, dict):
            return "", ""
        return str(status.get("SIGNAL_SERVICE_RET", "")), str(
            status.get("STATUS_RESULT_DESC", "")
        )

    def query_welfare(self, pid: int) -> WelfareStatus:
        out = JceOutputStream()
        out.write_struct_begin(0)
        self._write_user_id(out, 0)
        out.write_long(pid, 1)
        out.write_int(3, 2)
        out.write_struct_end()

        root, response = self._send_wup("wupui", "queryFansGroupTaskInfo", out.get_bytes())
        signal_code, _ = self._signal_status(root)
        response_wrapper = response.get("tRsp", {})
        payload = response_wrapper.get(0, {}) if isinstance(response_wrapper, dict) else {}
        day_welfare = payload.get(7, {}) if isinstance(payload, dict) else {}
        return WelfareStatus(
            signal_code=signal_code,
            business_code=int(payload.get(0, -1)) if isinstance(payload, dict) else -1,
            state=int(day_welfare.get(0, 0)) if isinstance(day_welfare, dict) else 0,
        )

    def claim_welfare(self, pid: int) -> ClaimResponse:
        out = JceOutputStream()
        out.write_struct_begin(0)
        self._write_user_id(out, 0)
        out.write_long(pid, 1)
        out.write_int(3, 2)
        out.write_struct_end()

        root, response = self._send_wup("wupui", "operateFansBox", out.get_bytes())
        signal_code, signal_description = self._signal_status(root)
        response_wrapper = response.get("tRsp", {})
        payload = response_wrapper.get(0, {}) if isinstance(response_wrapper, dict) else {}
        business_code = payload.get(0) if isinstance(payload, dict) else None
        item_count = payload.get(5, 0) if isinstance(payload, dict) else 0
        return ClaimResponse(
            signal_code=signal_code,
            signal_description=signal_description,
            business_code=int(business_code) if isinstance(business_code, int) else None,
            item_count=int(item_count) if isinstance(item_count, int) else 0,
        )


class PackageGiftClient(HuyaWupClient):
    """使用网页 H5 对应的 WUP 接口查询包裹并赠送虎粮。"""

    SEQUENCE_APP_KEY = "AzCXiouW6aLc4AsVGKAOOLlNLawNQsuV"
    CONSUME_GIFT_KEY = "Hi2UfWa8LhRM07ZjucWL9wzuX7okmGvd"
    WEB_UA = "webh5&1.0.0&huya"
    FROM_TYPE = 5
    BUSINESS_TYPE = 1

    def __init__(self, cookie_text: str):
        self.cookies = parse_cookie(cookie_text)
        super().__init__(cookie_text)
        if self.uid <= 0:
            raise ValueError("Cookie 中缺少有效的 yyuid/udb_uid")
        self.web_user_id_bytes = self._encode_web_user_id()

    def _encode_web_user_id(self) -> bytes:
        out = JceOutputStream()
        out.write_struct_begin(0)
        out.write_long(self.uid, 0)
        out.write_string("", 1)
        out.write_string("", 2)
        out.write_string(self.WEB_UA, 3)
        out.write_string(self.cookie_str, 4)
        out.write_int(0, 5)
        out.write_struct_end()
        return out.get_bytes()

    def _write_web_user_id(self, out: JceOutputStream, tag: int) -> None:
        out.write_struct_begin(tag)
        out.buf.write(self.web_user_id_bytes[1:-1])
        out.write_struct_end()

    @staticmethod
    def _signal_code(root: dict[int, Any]) -> str:
        status = root.get(10, {})
        return str(status.get("SIGNAL_SERVICE_RET", "")) if isinstance(status, dict) else ""

    def query_tiger_food(self, pid: int) -> PackageInventory:
        out = JceOutputStream()
        out.write_struct_begin(0)
        self._write_web_user_id(out, 0)
        out.write_long(pid, 1)
        out.write_struct_end()

        root, response = self._send_wup("wupui", "getPackageGift", out.get_bytes())
        signal_code = self._signal_code(root)
        response_wrapper = response.get("tRsp", {})
        payload = response_wrapper.get(0, {}) if isinstance(response_wrapper, dict) else {}
        gifts = payload.get(0, []) if isinstance(payload, dict) else []

        for gift in gifts if isinstance(gifts, list) else []:
            if not isinstance(gift, dict):
                continue
            simple_info = gift.get(0, {})
            if not isinstance(simple_info, dict):
                continue
            item_name = str(simple_info.get(3, ""))
            if item_name == "虎粮":
                return PackageInventory(
                    signal_code=signal_code,
                    item_type=int(simple_info.get(0, 0)),
                    item_name=item_name,
                    count=int(gift.get(5, 0)),
                )

        return PackageInventory(
            signal_code=signal_code,
            item_type=0,
            item_name="虎粮",
            count=0,
        )

    def _get_sequence(self) -> str:
        sequence_sign = hashlib.md5(
            (
                f"{self.uid}1{self.FROM_TYPE}{self.BUSINESS_TYPE}"
                f"{self.SEQUENCE_APP_KEY}"
            ).encode("utf-8")
        ).hexdigest()

        out = JceOutputStream()
        out.write_struct_begin(0)
        self._write_web_user_id(out, 0)
        out.write_int(1, 1)
        out.write_int(self.FROM_TYPE, 2)
        out.write_int(self.BUSINESS_TYPE, 3)
        out.write_string(sequence_sign, 4)
        out.write_struct_end()

        root, response = self._send_wup("sequenceui", "getSequence", out.get_bytes())
        signal_code = self._signal_code(root)
        response_wrapper = response.get("tRsp", {})
        payload = response_wrapper.get(0, {}) if isinstance(response_wrapper, dict) else {}
        ret_code = int(payload.get(0, -1)) if isinstance(payload, dict) else -1
        sequence = str(payload.get(1, "")) if isinstance(payload, dict) else ""
        if signal_code != "0" or ret_code != 0 or not sequence:
            raise RuntimeError(
                f"获取送礼序列号失败（协议码 {signal_code or '缺失'}，业务码 {ret_code}）"
            )
        return sequence

    def send_tiger_food(
        self,
        pid: int,
        item_type: int,
        count: int,
    ) -> GiftSendResponse:
        if pid <= 0 or item_type <= 0 or count <= 0:
            raise ValueError("主播 PID、虎粮道具 ID 和赠送数量必须为正整数")

        pay_id = self._get_sequence()
        passport = self.cookies.get("username", "")
        room_id = 0
        show_free_item_info = 0
        pay_policy = 2
        template_type = 5
        event_type = 2
        sign_source = "".join(
            str(value)
            for value in (
                self.uid,
                room_id,
                show_free_item_info,
                item_type,
                count,
                pid,
                pay_id,
                pay_policy,
                self.FROM_TYPE,
                template_type,
                passport,
                event_type,
                self.CONSUME_GIFT_KEY,
            )
        )
        gift_sign = hashlib.md5(sign_source.encode("utf-8")).hexdigest()

        out = JceOutputStream()
        out.write_struct_begin(0)
        self._write_web_user_id(out, 0)
        out.write_long(room_id, 1)
        out.write_int(show_free_item_info, 2)
        out.write_int(item_type, 3)
        out.write_int(count, 4)
        out.write_long(pid, 5)
        out.write_long(pid, 6)
        out.write_string(pay_id, 7)
        out.write_string("", 8)
        out.write_int(pay_policy, 9)
        out.write_int(self.FROM_TYPE, 10)
        out.write_string("", 11)
        out.write_int(template_type, 12)
        out.write_string(passport, 13)
        out.write_short(event_type, 14)
        out.write_string(gift_sign, 15)
        out.write_int(0, 16)
        out.write_int(0, 17)
        out.write_int(0, 18)
        out.write_map_str_str({}, 19)
        out.write_string("", 20)
        out.write_string("", 21)
        out.write_struct_end()

        root, response = self._send_wup(
            "PropsUIServer", "consumeGiftSafe", out.get_bytes()
        )
        response_wrapper = response.get("tRsp", {})
        payload = response_wrapper.get(0, {}) if isinstance(response_wrapper, dict) else {}
        return GiftSendResponse(
            signal_code=self._signal_code(root),
            pay_code=int(payload.get(0, -1)) if isinstance(payload, dict) else -1,
            item_type=int(payload.get(1, 0)) if isinstance(payload, dict) else 0,
            item_count=int(payload.get(2, 0)) if isinstance(payload, dict) else 0,
            message=str(payload.get(11, "")) if isinstance(payload, dict) else "",
        )



class HuyaMobileBotV2:
    """虎牙 v2 移动 App 端自动化机器人"""

    def __init__(self, config: Optional[dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.room_url = self.config["ROOM_URL"]
        self.account = self.config["ACCOUNT"]
        self.cookie_str = self.config["COOKIE"] or load_cookie_from_files(
            self.config["COOKIE_FILE"]
        )
        self.gift_count = self.config["GIFT_COUNT"]
        self.do_daka = self.config["DO_DAKA"]
        self.do_welfare = self.config["DO_WELFARE"]
        self.wechat_push = self.config["WECHAT_PUSH"]

        self.room_info = fetch_room_metadata_http(self.room_url) if self.room_url else DEFAULT_ROOM_DEFAULTS
        self.pid = int(self.room_info.get("lp") or 0)
        self.wup_client: Optional[HuyaWupClient] = None
        self.welfare_client: Optional[DailyTigerFoodClient] = None
        self.package_client: Optional[PackageGiftClient] = None

    def ensure_logged_in(self) -> bool:
        """仅通过 WUP 校验 Cookie，并初始化全部协议客户端。"""
        if not self.cookie_str:
            log("ERROR", "V2 必须配置有效 Cookie，不支持浏览器或账号密码登录回退。")
            return False

        try:
            self.wup_client = HuyaWupClient(self.cookie_str)
            self.welfare_client = DailyTigerFoodClient(self.cookie_str)
            self.package_client = PackageGiftClient(self.cookie_str)
            inventory = self.package_client.query_tiger_food(self.pid)
            if inventory.signal_code != "0":
                log(
                    "ERROR",
                    f"Cookie WUP 校验失败（协议码 {inventory.signal_code or '缺失'}）。",
                )
                return False
            log(
                "SUCCESS",
                f"Cookie WUP 协议验证成功！(UID: {self.wup_client.uid}，虎粮库存: {inventory.count})",
            )
            return True
        except Exception as exc:
            log("ERROR", f"Cookie WUP 校验异常: {exc}")
            self.wup_client = None
            self.welfare_client = None
            self.package_client = None
            return False

    def query_badge_wup(self) -> dict:
        """通过官方 WUP 协议精准查询勋章与亲密度数据"""
        badge_data = {
            "fans_level": "未知",
            "need_intimacy": "未知",
            "intimacy_progress": "",
            "badge_name": "",
            "today_score": 0,
            "quota_score": 0,
            "raw": None
        }

        if self.wup_client:
            try:
                badge = self.wup_client.query_badge_info(self.pid)
                if badge:
                    badge_data["fans_level"] = badge.get("level_str", "未知")
                    badge_data["need_intimacy"] = str(badge.get("need_score", "未知"))
                    badge_data["intimacy_progress"] = badge.get("progress_str", "")
                    badge_data["badge_name"] = badge.get("badge_name", "")
                    badge_data["today_score"] = badge.get("today_score", 0)
                    badge_data["quota_score"] = badge.get("quota_score", 0)
                    badge_data["raw"] = badge
                    log("INFO", f"【WUP 官方勋章数据】勋章: [{badge.get('badge_name')}] | 等级: {badge_data['fans_level']} | 升级还需: {badge_data['need_intimacy']} 亲密度（进度: {badge_data['intimacy_progress']}）| 今日亲密度: {badge.get('today_score')}/{badge.get('quota_score')}")
                    return badge_data
            except Exception as e:
                log("WARN", f"WUP 查询勋章数据异常: {e}")

        return badge_data

    def mobile_punch_card(self) -> dict:
        """执行移动端 WUP 纯协议打卡 (+5 亲密度)"""
        nick = self.room_info.get("nick") or "目标主播"
        log("INFO", f"使用 WUP 移动端官方协议执行主播 [{nick}] 粉丝团打卡...")

        result = {
            "success": False,
            "status": "未完成",
            "detail": "未完成"
        }

        if not self.wup_client:
            result["detail"] = "WUP 客户端未初始化"
            return result

        try:
            badge_before = self.wup_client.query_badge_info(self.pid)
            sign_res = self.wup_client.fans_sign(self.pid)
            if not sign_res.success:
                log("WARN", f"WUP 移动端打卡返回: {sign_res.message}")
                result["detail"] = sign_res.message or "打卡返回异常"
                return result

            if sign_res.already_signed:
                result["success"] = True
                result["status"] = "今日已打卡"
                result["detail"] = "今日已经完成粉丝团打卡，无需重复领取"
                log("SUCCESS", result["detail"])
                return result

            observed_add = 0
            if badge_before:
                before_score = int(badge_before.get("current_score", 0))
                for attempt in range(3):
                    if attempt:
                        time.sleep(0.5)
                    badge_after = self.wup_client.query_badge_info(self.pid)
                    if badge_after:
                        observed_add = max(
                            0, int(badge_after.get("current_score", 0)) - before_score
                        )
                        if observed_add >= sign_res.intimacy_add:
                            break

            add_pt = observed_add or sign_res.intimacy_add
            detail_str = f"打卡成功（亲密度+{add_pt}，状态复查已确认）"
            log("SUCCESS", f"🎉 WUP 移动端打卡成功！{detail_str}")
            result["success"] = True
            result["status"] = "打卡成功"
            result["detail"] = detail_str
        except Exception as e:
            log("ERROR", f"WUP 移动端打卡抛出异常: {e}")
            result["detail"] = f"打卡异常: {e}"

        return result

    def claim_mobile_welfare(self) -> dict:
        """
        处理移动端专属每日福利（10 虎粮）：
        1. queryFansGroupTaskInfo 查状态；
        2. operateFansBox 尝试领取并处理响应；
        """
        log("INFO", "正在检查移动端粉丝团专属每日福利（虎粮 x10）状态...")
        result = {
            "success": False,
            "status": "未领取",
            "detail": "未领取",
            "item_count": 0
        }

        if not self.welfare_client:
            result["detail"] = "WUP 客户端未就绪"
            return result

        try:
            # 1. 探查任务状态
            before = self.welfare_client.query_welfare(self.pid)
            if before.signal_code != "0" or before.business_code != 0:
                result["detail"] = f"福利状态查询失败（协议码 {before.signal_code or '缺失'}）"
                return result
            log("INFO", f"【移动端福利探查】当前状态: {before.description} (状态码: {before.state})")

            if before.state == 4:
                result["success"] = True
                result["status"] = "今日已领"
                result["detail"] = "今日已领取过 10 虎粮福利"
                log("SUCCESS", "移动端专属福利: 今日已领取")
                return result

            if before.state != 3:
                result["detail"] = f"当前不可领取：{before.description}"
                return result

            # 2. 执行领取尝试
            log("INFO", "发起移动端专属福利领取请求 (wupui.operateFansBox)...")
            claim = self.welfare_client.claim_welfare(self.pid)

            if claim.signal_code != "0":
                result["detail"] = (
                    f"领取失败：协议状态码 {claim.signal_code}"
                    f"{f'，{claim.signal_description}' if claim.signal_description else ''}"
                )
                return result
            if claim.business_code not in (None, 0):
                result["detail"] = f"领取失败：业务状态码 {claim.business_code}"
                return result

            after = None
            for attempt in range(3):
                if attempt:
                    time.sleep(0.5)
                after = self.welfare_client.query_welfare(self.pid)
                if after.signal_code != "0" or after.business_code != 0:
                    result["detail"] = "领取后状态查询失败"
                    return result
                if after.state == 4:
                    break
            if after is None or after.state != 4:
                result["detail"] = "领取响应未被状态查询确认"
                return result

            item_count = claim.item_count or 10
            result["success"] = True
            result["item_count"] = item_count
            result["status"] = "领取成功"
            result["detail"] = f"成功领取移动端专属福利（虎粮 x{item_count}）"
            log("SUCCESS", f"🎉 {result['detail']}")

        except Exception as e:
            log("ERROR", f"移动端福利操作异常: {e}")
            result["detail"] = f"福利领取异常: {e}"

        return result

    def send_tiger_food(self) -> dict:
        """通过纯 WUP 协议查询库存、赠送虎粮并复查实际余量。"""
        nick = self.room_info.get("nick") or "目标主播"
        result = {
            "success": False,
            "count": 0,
            "left_count": None,
            "status": "未完成",
            "detail": ""
        }
        if not self.package_client:
            result["detail"] = "包裹 WUP 客户端未就绪"
            return result

        try:
            before = self.package_client.query_tiger_food(self.pid)
            if before.signal_code != "0":
                result["detail"] = (
                    f"虎粮库存查询失败（协议码 {before.signal_code or '缺失'}）"
                )
                return result

            result["left_count"] = before.count
            log("INFO", f"【WUP 包裹检查】当前虎粮库存: {before.count} 个")
            if before.count <= 0:
                result.update(
                    success=True,
                    status="暂无虎粮",
                    detail="包裹中暂无虎粮",
                )
                return result
            if before.item_type <= 0:
                result["detail"] = "查询到虎粮库存，但未取得有效道具 ID"
                return result

            send_count = (
                min(self.gift_count, before.count)
                if self.gift_count > 0
                else before.count
            )
            log(
                "INFO",
                f"准备通过 WUP 向主播 [{nick}] 赠送 {send_count} 个虎粮"
                f"（赠送前库存: {before.count}）",
            )
            response = self.package_client.send_tiger_food(
                self.pid, before.item_type, send_count
            )
            if response.signal_code != "0" or response.pay_code != 0:
                response_detail = f"，{response.message}" if response.message else ""
                result["detail"] = (
                    f"送粮失败（协议码 {response.signal_code or '缺失'}，"
                    f"支付码 {response.pay_code}{response_detail}）"
                )
                return result

            after = None
            expected_count = before.count - send_count
            for attempt in range(3):
                if attempt:
                    time.sleep(0.5)
                candidate = self.package_client.query_tiger_food(self.pid)
                if candidate.signal_code == "0":
                    after = candidate
                    if after.count == expected_count:
                        break

            if after is None:
                result["detail"] = "送粮请求成功，但赠送后库存复查失败"
                return result

            result["left_count"] = after.count
            if after.count != expected_count:
                result["detail"] = (
                    f"送粮结果未通过库存复查：赠送前 {before.count}，"
                    f"计划赠送 {send_count}，实际剩余 {after.count}"
                )
                return result

            result.update(
                success=True,
                count=send_count,
                status="赠送成功",
                detail=(
                    f"成功送出 {send_count} 个虎粮（库存 {before.count} → {after.count}）"
                ),
            )
            log("SUCCESS", f"🎉 {result['detail']}")
            return result
        except Exception as exc:
            log("ERROR", f"WUP 送虎粮过程异常: {exc}")
            result["detail"] = f"送礼异常: {exc}"
            return result

    def execute(self) -> dict:
        """运行 v2 完整流程"""
        log("INFO", "========== 启动虎牙每日自动助手 v2 ==========")
        log("INFO", f"当前执行账号: [{mask_account(self.account)}]")
        summary = {
            "version": "v2 (全自动福利版)",
            "nick": self.room_info.get("nick") or "目标主播",
            "room_id": str(self.room_info.get("profileRoom") or "未知"),
            "account": self.account,
            "daka_success": False,
            "daka_detail": "跳过打卡",
            "welfare_success": False,
            "welfare_detail": "跳过福利",
            "gift_success": False,
            "gift_detail": "未赠送",
            "left_count": None,
            "fans_level": "",
            "need_intimacy": "",
            "intimacy_progress": "",
            "today_score": "",
            "today_quota": "",
            "all_success": False
        }

        logged_in = self.ensure_logged_in()
        if not logged_in:
            summary["daka_detail"] = "登录失败"
            summary["welfare_detail"] = "登录失败"
            summary["gift_detail"] = "登录失败"
        else:
            if self.do_daka:
                daka_res = self.mobile_punch_card()
                summary["daka_success"] = daka_res.get("success", False)
                summary["daka_detail"] = daka_res.get("detail", "")
            else:
                summary["daka_success"] = True
                summary["daka_detail"] = "配置跳过打卡"

            if self.do_welfare:
                welfare_res = self.claim_mobile_welfare()
                summary["welfare_success"] = welfare_res.get("success", False)
                summary["welfare_detail"] = welfare_res.get("detail", "")
            else:
                summary["welfare_success"] = True
                summary["welfare_detail"] = "配置跳过福利"

            gift_res = self.send_tiger_food()
            summary["gift_success"] = gift_res.get("success", False)
            summary["gift_detail"] = gift_res.get("detail", "")
            summary["left_count"] = gift_res.get("left_count")

            badge_info = self.query_badge_wup()
            summary["fans_level"] = badge_info.get("fans_level", "")
            summary["badge_name"] = badge_info.get("badge_name", "")
            summary["need_intimacy"] = badge_info.get("need_intimacy", "")
            summary["intimacy_progress"] = badge_info.get("intimacy_progress", "")
            raw = badge_info.get("raw") or {}
            summary["current_score"] = raw.get("current_score")
            summary["next_score"] = raw.get("next_score")
            summary["today_score"] = str(badge_info.get("today_score", ""))
            summary["today_quota"] = str(badge_info.get("quota_score", ""))

            summary["all_success"] = all((
                summary["daka_success"],
                summary["welfare_success"],
                summary["gift_success"],
            ))

        if self.wechat_push:
            push_wecom_message(summary, self.config)
        else:
            log("INFO", "企业微信推送已禁用。")
        log("INFO", "========== 虎牙助手 v2 移动 App 端运行结束 ==========")
        return summary


def run(args=None) -> dict:
    """外部总入口调用的主函数"""
    config = DEFAULT_CONFIG.copy()
    if args:
        config.update({
            "GIFT_COUNT": getattr(args, "count", config["GIFT_COUNT"]),
            "ROOM_URL": getattr(args, "room", None) or config["ROOM_URL"],
            "DO_DAKA": getattr(args, "do_daka", not getattr(args, "no_daka", False)),
            "DO_WELFARE": getattr(args, "do_welfare", not getattr(args, "no_welfare", False)),
            "WECHAT_PUSH": getattr(args, "wechat_push", config["WECHAT_PUSH"]),
            "ACCOUNT": getattr(args, "account", config["ACCOUNT"]),
            "COOKIE": getattr(args, "cookie", config["COOKIE"]),
            "COOKIE_FILE": getattr(args, "cookie_file", config["COOKIE_FILE"]),
            "WX_WEBHOOK": getattr(args, "wx_webhook", config["WX_WEBHOOK"]),
        })

    bot = HuyaMobileBotV2(config)
    return bot.execute()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="虎牙每日自动助手 v2 (移动 App 端)")
    parser.add_argument("-c", "--count", type=int, default=0, help="赠送虎粮数量 (0 为全部送出，默认 0)")
    parser.add_argument("--no-daka", action="store_true", help="跳过每日打卡")
    parser.add_argument("--no-welfare", action="store_true", help="跳过粉丝团专属福利领取")
    parser.add_argument("--room", type=str, default=None, help="目标直播间 URL")
    cli_args = parser.parse_args()

    run(cli_args)
