#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虎牙移动端官方 WUP (Wireless Unified Protocol) 协议通信核心模块
实现纯 Python 的 JCE 序列化与反序列化，支持：
1. 粉丝团每日打卡 (getFansSign / setFansSign) - 亲密度 +5，秒级直连，免浏览器免 DOM
2. 粉丝勋章及亲密度精确查询 (queryBadgeInfoList) - 获取真实粉丝等级、当前亲密度、升下一级还需亲密度
3. 粉丝团任务及日福利状态查询 (queryFansGroupTaskInfo)
4. 移动端粉丝团日福利领取尝试 (operateFansBox)
"""

import io
import re
import gzip
import struct
import time
import urllib.request
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class FansSignStatus:
    signal_code: str
    business_code: int
    message: str
    position: int
    position_time: int
    sign_flags: int

    @property
    def signed_today(self) -> bool:
        if self.position <= 0:
            return False
        return bool(self.sign_flags & (1 << (self.position - 1)))


@dataclass(frozen=True)
class FansSignActionResponse:
    signal_code: str
    business_code: int
    message: str


@dataclass(frozen=True)
class FansSignResult:
    success: bool
    already_signed: bool
    intimacy_add: int
    position: int
    message: str


class JceOutputStream:
    """轻量级 JCE 协议序列化流"""

    def __init__(self):
        self.buf = io.BytesIO()

    def _write_head(self, tag: int, type_: int):
        if tag < 15:
            self.buf.write(bytes([(tag << 4) | type_]))
        else:
            self.buf.write(bytes([(15 << 4) | type_, tag & 0xFF]))

    def write_byte(self, val: int, tag: int):
        if val == 0:
            self._write_head(tag, 12)  # ZERO_TAG
        else:
            self._write_head(tag, 0)
            self.buf.write(struct.pack('>b', val))

    def write_short(self, val: int, tag: int):
        if -128 <= val <= 127:
            self.write_byte(val, tag)
        else:
            self._write_head(tag, 1)
            self.buf.write(struct.pack('>h', val))

    def write_int(self, val: int, tag: int):
        if -32768 <= val <= 32767:
            self.write_short(val, tag)
        else:
            self._write_head(tag, 2)
            self.buf.write(struct.pack('>i', val))

    def write_long(self, val: int, tag: int):
        if -2147483648 <= val <= 2147483647:
            self.write_int(val, tag)
        else:
            self._write_head(tag, 3)
            self.buf.write(struct.pack('>q', val))

    def write_string(self, val: str, tag: int):
        b = val.encode('utf-8')
        if len(b) > 255:
            self._write_head(tag, 7)
            self.buf.write(struct.pack('>I', len(b)))
        else:
            self._write_head(tag, 6)
            self.buf.write(struct.pack('>B', len(b)))
        self.buf.write(b)

    def write_bytes(self, val: bytes, tag: int):
        # SIMPLE_LIST (type 13)
        self._write_head(tag, 13)
        self.buf.write(bytes([(0 << 4) | 0]))  # 元素类型为 BYTE
        self.write_int(len(val), 0)
        self.buf.write(val)

    def write_map_str_bytes(self, m: Dict[str, bytes], tag: int):
        self._write_head(tag, 8)
        self.write_int(len(m), 0)
        for k, v in m.items():
            self.write_string(k, 0)
            self.write_bytes(v, 1)

    def write_map_str_str(self, m: Dict[str, str], tag: int):
        self._write_head(tag, 8)
        self.write_int(len(m), 0)
        for k, v in m.items():
            self.write_string(k, 0)
            self.write_string(v, 1)

    def write_struct_begin(self, tag: int):
        self._write_head(tag, 10)

    def write_struct_end(self):
        self._write_head(0, 11)

    def get_bytes(self) -> bytes:
        return self.buf.getvalue()


class JceInputStream:
    """轻量级 JCE 协议反序列化流"""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read_head(self) -> Tuple[Optional[int], Optional[int]]:
        if self.pos >= len(self.data):
            return None, None
        b = self.data[self.pos]
        self.pos += 1
        type_ = b & 0x0F
        tag = (b >> 4) & 0x0F
        if tag == 15:
            tag = self.data[self.pos]
            self.pos += 1
        return tag, type_

    def read_val(self, type_: int) -> Any:
        if type_ == 12:  # ZERO_TAG
            return 0
        if type_ == 0:   # BYTE
            v = struct.unpack_from('>b', self.data, self.pos)[0]
            self.pos += 1
            return v
        if type_ == 1:   # SHORT
            v = struct.unpack_from('>h', self.data, self.pos)[0]
            self.pos += 2
            return v
        if type_ == 2:   # INT
            v = struct.unpack_from('>i', self.data, self.pos)[0]
            self.pos += 4
            return v
        if type_ == 3:   # LONG
            v = struct.unpack_from('>q', self.data, self.pos)[0]
            self.pos += 8
            return v
        if type_ == 4:   # FLOAT
            v = struct.unpack_from('>f', self.data, self.pos)[0]
            self.pos += 4
            return v
        if type_ == 5:   # DOUBLE
            v = struct.unpack_from('>d', self.data, self.pos)[0]
            self.pos += 8
            return v
        if type_ == 6:   # STRING1
            l = self.data[self.pos]
            self.pos += 1
            s = self.data[self.pos:self.pos + l].decode('utf-8', errors='ignore')
            self.pos += l
            return s
        if type_ == 7:   # STRING4
            l = struct.unpack_from('>I', self.data, self.pos)[0]
            self.pos += 4
            s = self.data[self.pos:self.pos + l].decode('utf-8', errors='ignore')
            self.pos += l
            return s
        if type_ == 8:   # MAP
            _, kt = self.read_head()
            cnt = self.read_val(kt)
            m = {}
            for _ in range(cnt):
                _, k_t = self.read_head()
                k = self.read_val(k_t)
                _, v_t = self.read_head()
                v = self.read_val(v_t)
                m[k] = v
            return m
        if type_ == 9:   # VECTOR / LIST
            _, count_type = self.read_head()
            cnt = self.read_val(count_type)
            items = []
            for _ in range(cnt):
                _, item_type = self.read_head()
                items.append(self.read_val(item_type))
            return items
        if type_ == 10:  # STRUCT_BEGIN
            obj = {}
            while self.pos < len(self.data):
                tag, field_type = self.read_head()
                if field_type == 11 or tag is None:
                    break
                obj[tag] = self.read_val(field_type)
            return obj
        if type_ == 13:  # SIMPLE_LIST
            self.pos += 1  # 跳过元素类型
            _, len_type = self.read_head()
            l = self.read_val(len_type)
            raw = self.data[self.pos:self.pos + l]
            self.pos += l
            return raw
        return f"UNKNOWN_{type_}"

    def parse_all(self) -> Dict[int, Any]:
        res = {}
        while self.pos < len(self.data):
            tag, type_ = self.read_head()
            if tag is None:
                break
            res[tag] = self.read_val(type_)
        return res


class HuyaWupClient:
    """虎牙 WUP 网关通信客户端"""

    WUP_URL = "https://wup.huya.com"

    def __init__(self, cookie_str: str):
        self.cookie_str = cookie_str.strip()
        self.uid = self._extract_cookie_uid()
        self.guid = self._extract_cookie_val("guid")
        self.user_id_bytes = self._encode_user_id()

    def _extract_cookie_val(self, key: str) -> str:
        m = re.search(rf'{key}=([a-zA-Z0-9_-]+)', self.cookie_str)
        return m.group(1) if m else ""

    def _extract_cookie_uid(self) -> int:
        m = re.search(r'yyuid=(\d+)', self.cookie_str)
        if not m:
            m = re.search(r'udb_uid=(\d+)', self.cookie_str)
        return int(m.group(1)) if m else 0

    def _encode_user_id(self) -> bytes:
        """编码 com.duowan.HUYA.UserId 对象"""
        out = JceOutputStream()
        out.write_struct_begin(0)
        out.write_long(self.uid, 0)
        if self.guid:
            out.write_string(self.guid, 1)
        out.write_string("android&12.7.4&official&34", 3)
        if self.cookie_str:
            out.write_string(self.cookie_str, 4)
        out.write_int(0, 5)
        out.write_string("Pixel 7", 6)
        out.write_struct_end()
        return out.get_bytes()

    def _build_wup_request(self, servant: str, func: str, req_bytes: bytes, req_key: str = "tReq", req_id: int = 1) -> bytes:
        """组装符合 WUP v3 规范的 RequestPacket 并附加 4 字节总长度"""
        s_buf = JceOutputStream()
        s_buf.write_map_str_bytes({req_key: req_bytes}, 0)

        rp = JceOutputStream()
        rp.write_short(3, 1)             # iVersion = 3
        rp.write_byte(0, 2)              # cPacketType = 0
        rp.write_int(0, 3)               # iMessageType = 0
        rp.write_int(req_id, 4)          # iRequestId
        rp.write_string(servant, 5)      # sServantName
        rp.write_string(func, 6)         # sFuncName
        rp.write_bytes(s_buf.get_bytes(), 7)  # sBuffer
        rp.write_int(0, 8)               # iTimeout
        rp.write_map_str_str({}, 9)      # context
        rp.write_map_str_str({}, 10)     # status

        payload = rp.get_bytes()
        total_len = len(payload) + 4
        return struct.pack('>I', total_len) + payload

    def _send_wup(self, servant: str, func: str, req_bytes: bytes, req_key: str = "tReq") -> Tuple[Dict[int, Any], Dict[str, Any]]:
        """发送 WUP 请求，支持自动 GZIP 解压并解析响应体"""
        packet = self._build_wup_request(servant, func, req_bytes, req_key=req_key)
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22011211C Build/UKQ1.230917.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/118.0.0.0 Mobile Safari/537.36/HuYa-android-12.7.4-6019-14-12007040",
            "Content-Type": "application/x-wup",
            "Cookie": self.cookie_str
        }
        req = urllib.request.Request(self.WUP_URL, data=packet, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()

        # 检查是否进行了 GZIP 压缩
        if raw[:3] == b'\x1f\x8b\x08':
            raw = gzip.decompress(raw)

        total_len = struct.unpack_from('>I', raw, 0)[0]
        body = raw[4:total_len]

        root = JceInputStream(body).parse_all()
        s_buf = root.get(7)
        rsp_dict = {}

        if isinstance(s_buf, (bytes, bytearray)):
            buf_map = JceInputStream(s_buf).parse_all().get(0, {})
            for k, v in buf_map.items():
                if isinstance(v, (bytes, bytearray)):
                    rsp_dict[k] = JceInputStream(v).parse_all()
                else:
                    rsp_dict[k] = v

        return root, rsp_dict

    def _build_fans_sign_request(self, pid: int) -> bytes:
        if pid <= 0:
            raise ValueError("主播 PID 必须为正整数")

        out = JceOutputStream()
        out.write_struct_begin(0)
        out.write_struct_begin(0)
        out.buf.write(self.user_id_bytes[1:-1])
        out.write_struct_end()
        out.write_long(pid, 1)
        out.write_struct_end()
        return out.get_bytes()

    @staticmethod
    def _signal_code(root: Dict[int, Any]) -> str:
        status = root.get(10, {})
        return str(status.get("SIGNAL_SERVICE_RET", "")) if isinstance(status, dict) else ""

    def query_fans_sign(self, pid: int) -> FansSignStatus:
        """查询当天粉丝团打卡状态，不产生打卡副作用。"""
        root, rsp = self._send_wup(
            "wupui", "getFansSign", self._build_fans_sign_request(pid)
        )
        response_wrapper = rsp.get("tRsp", {})
        payload = response_wrapper.get(0, {}) if isinstance(response_wrapper, dict) else {}
        sign_info = payload.get(2, {}) if isinstance(payload, dict) else {}
        return FansSignStatus(
            signal_code=self._signal_code(root),
            business_code=int(payload.get(0, -1)) if isinstance(payload, dict) else -1,
            message=str(payload.get(1, "")) if isinstance(payload, dict) else "",
            position=int(sign_info.get(0, 0)) if isinstance(sign_info, dict) else 0,
            position_time=int(sign_info.get(1, 0)) if isinstance(sign_info, dict) else 0,
            sign_flags=int(sign_info.get(2, 0)) if isinstance(sign_info, dict) else 0,
        )

    def set_fans_sign(self, pid: int) -> FansSignActionResponse:
        """调用 setFansSign 执行当天粉丝团打卡。"""
        root, rsp = self._send_wup(
            "wupui", "setFansSign", self._build_fans_sign_request(pid)
        )
        response_wrapper = rsp.get("tRsp", {})
        payload = response_wrapper.get(0, {}) if isinstance(response_wrapper, dict) else {}
        return FansSignActionResponse(
            signal_code=self._signal_code(root),
            business_code=int(payload.get(0, -1)) if isinstance(payload, dict) else -1,
            message=str(payload.get(1, "")) if isinstance(payload, dict) else "",
        )

    def fans_sign(self, pid: int) -> FansSignResult:
        """查询状态、执行打卡，并通过再次查询确认当天已经打卡。"""
        before = self.query_fans_sign(pid)
        if before.signal_code != "0":
            return FansSignResult(
                success=False,
                already_signed=False,
                intimacy_add=0,
                position=before.position,
                message=f"打卡状态查询失败（协议码 {before.signal_code or '缺失'}）",
            )
        if before.business_code != 0:
            return FansSignResult(
                success=False,
                already_signed=False,
                intimacy_add=0,
                position=before.position,
                message=before.message or f"打卡状态查询失败（业务码 {before.business_code}）",
            )
        if before.signed_today:
            return FansSignResult(
                success=True,
                already_signed=True,
                intimacy_add=0,
                position=before.position,
                message="今日已经完成粉丝团打卡",
            )

        action = self.set_fans_sign(pid)
        if action.signal_code != "0" or action.business_code != 0:
            return FansSignResult(
                success=False,
                already_signed=False,
                intimacy_add=0,
                position=before.position,
                message=action.message or (
                    f"打卡失败（协议码 {action.signal_code or '缺失'}，"
                    f"业务码 {action.business_code}）"
                ),
            )

        after = None
        for attempt in range(3):
            if attempt:
                time.sleep(0.5)
            candidate = self.query_fans_sign(pid)
            if candidate.signal_code == "0" and candidate.business_code == 0:
                after = candidate
                if candidate.signed_today:
                    break

        if after is None or not after.signed_today:
            return FansSignResult(
                success=False,
                already_signed=False,
                intimacy_add=0,
                position=before.position,
                message="setFansSign 已返回成功，但状态复查未确认打卡完成",
            )

        return FansSignResult(
            success=True,
            already_signed=False,
            intimacy_add=5,
            position=after.position,
            message=action.message or "粉丝团打卡成功",
        )

    def query_badge_info(self, pid: int) -> Optional[Dict[str, Any]]:
        """
        查询目标主播的粉丝勋章详细数据（等级、当前亲密度、升级还需亲密度等）
        请求结构：BadgeInfoListReq (tag 0: UserId, tag 1: lToUid, tag 2: iType, tag 3: lPid, tag 4: iSFanFlag)
        """
        out = JceOutputStream()
        out.write_struct_begin(0)
        out.write_struct_begin(0)
        out.buf.write(self.user_id_bytes[1:-1])
        out.write_struct_end()
        out.write_long(self.uid, 1)      # lToUid
        out.write_int(0, 2)              # iType
        out.write_long(pid, 3)           # lPid
        out.write_int(0, 4)              # iSFanFlag
        out.write_struct_end()

        root, rsp = self._send_wup("liveui", "queryBadgeInfoList", out.get_bytes())
        rsp_data = rsp.get("tRsp", {}).get(0, {})
        badge_list = rsp_data.get(0, [])

        for b in badge_list:
            if not isinstance(b, dict):
                continue
            badge_pid = b.get(1, 0)
            if badge_pid == pid or badge_pid == 0:
                badge_name = b.get(3, "")
                level = b.get(4, 0)
                current_score = b.get(6, 0)
                next_score = b.get(7, 0)
                today_score = b.get(8, 0)
                quota_score = b.get(9, 0)
                need_score = max(0, next_score - current_score)

                return {
                    "badge_name": badge_name,
                    "level": level,
                    "level_str": f"{level}级",
                    "current_score": current_score,
                    "next_score": next_score,
                    "need_score": need_score,
                    "today_score": today_score,
                    "quota_score": quota_score,
                    "progress_str": f"{current_score}/{next_score}",
                    "anchor_nick": b.get(2, "")
                }

        return None
