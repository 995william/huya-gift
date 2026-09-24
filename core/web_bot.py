#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虎牙每日自动助手 - v1 网页端版本 (Huya Web Bot v1)
功能特性：
1. 【网页端打卡】：自动化进入直播间，鼠标悬停输入框左侧粉丝徽章 (#chatHostPic)，呼出打卡浮层并点击打卡（亲密度 +5）。
2. 【包裹免费虎粮赠送】：访问主播专属包裹页面 (webPackageV2)，支持指定赠送数量或全部送出。
3. 【亲密度与等级提取】：精准提取当前粉丝等级、升级还需亲密度及经验总进度。
4. 【企业微信全文本推送】：严格采用全文本格式 (msgtype: text)，杜绝 Markdown 错乱。
5. 【完全独立运行】：既可被 main.py 统一调用，也可直接独立运行 `python huya_v1.py`。
"""

import os
import sys
import time
import re
import json
import ssl
import argparse
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 确保 Windows 终端标准输出编码正常
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ==================== 默认配置 ====================
DEFAULT_CONFIG = {
    "GIFT_COUNT": int(os.getenv("HUYA_GIFT_COUNT", "0").strip() or 0),
    "ROOM_URL": os.getenv("HUYA_ROOM_URL", "").strip(),
    "ACCOUNT": os.getenv("HUYA_ACCOUNT", "").strip(),
    "PASSWORD": os.getenv("HUYA_PASSWORD", "").strip(),
    "COOKIE": os.getenv("HUYA_COOKIE", "").strip(),
    "COOKIE_FILE": os.getenv("HUYA_COOKIE_FILE", "huya_cookie.txt").strip(),
    "HEADLESS": os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes"),
    "DO_DAKA": os.getenv("HUYA_DAKA", "true").lower() in ("true", "1", "yes"),
    "WECHAT_PUSH": os.getenv("HUYA_WECHAT_PUSH", "true").lower() in ("true", "1", "yes"),
    "WX_WEBHOOK": os.getenv("WX_WEBHOOK", "").strip(),
}

DEFAULT_ROOM_DEFAULTS = {
    "lp": "0",
    "gid": "0",
    "profileRoom": "未知",
    "nick": "目标主播",
}


# 引入公共基础库
from .common import (
    clean_daka_summary,
    clean_gift_summary,
    clean_welfare_summary,
    fetch_room_metadata_http,
    load_cookie_from_files,
    save_cookie_to_files,
    make_progress_bar,
    mask_account,
    parse_cookie,
    push_wecom_message,
)
from .common import log as common_log


def log(level: str, message: str) -> None:
    common_log("v1-Web", level, message)


class HuyaWebBotV1:
    """虎牙 v1 网页端自动化机器人"""

    def __init__(self, config: Optional[dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.room_url = self.config["ROOM_URL"]
        self.account = self.config["ACCOUNT"]
        self.password = self.config["PASSWORD"]
        self.cookie_str = self.config["COOKIE"] or load_cookie_from_files(
            self.config["COOKIE_FILE"]
        )
        self.headless = self.config["HEADLESS"]
        self.gift_count = self.config["GIFT_COUNT"]
        self.do_daka = self.config["DO_DAKA"]
        self.wechat_push = self.config["WECHAT_PUSH"]

        self.room_info = fetch_room_metadata_http(self.room_url)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def _init_browser(self):
        """初始化 Chromium 浏览器上下文"""
        if self.browser:
            return
        if not self.playwright:
            self.playwright = sync_playwright().start()

        mode_desc = "无头后台模式" if self.headless else "可视化窗口模式"
        log("INFO", f"启动 Chromium 浏览器 ({mode_desc})...")
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars"
            ]
        )
        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.page = self.context.new_page()

        if self.cookie_str:
            cookies_to_add = []
            for item in self.cookie_str.split(";"):
                if "=" in item:
                    k, v = item.strip().split("=", 1)
                    cookies_to_add.append({
                        "name": k.strip(),
                        "value": v.strip(),
                        "domain": ".huya.com",
                        "path": "/"
                    })
            if cookies_to_add:
                try:
                    self.context.add_cookies(cookies_to_add)
                except Exception as e:
                    log("WARN", f"注入 Cookie 失败: {e}")

    def _close_browser(self):
        """释放浏览器资源"""
        try:
            if self.browser:
                self.browser.close()
                self.browser = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
            log("INFO", "已释放浏览器资源。")
        except Exception:
            pass

    def ensure_logged_in(self) -> bool:
        """确保浏览器具备有效登录态"""
        self._init_browser()
        if self.cookie_str:
            self.page.goto("https://i.huya.com/", wait_until="domcontentloaded")
            time.sleep(3)
            body = self.page.inner_text("body")
            if any(kw in body for kw in ["虎牙号", "个人中心", "我的财产", "退出"]):
                log("SUCCESS", "网页端已有 Cookie 验证有效！")
                return True

        if not self.account or not self.password:
            log("ERROR", "未配置账号密码且本地 Cookie 无效！")
            return False

        log("INFO", f"正在使用账号 [{mask_account(self.account)}] 尝试密码登录...")
        self.page.goto("https://i.huya.com/", wait_until="domcontentloaded")
        time.sleep(2)

        try:
            iframe_elem = self.page.wait_for_selector("#UDBSdkLgn_iframe", timeout=15000)
            if not iframe_elem:
                log("ERROR", "未找到登录 iframe 弹窗")
                return False
            frame = iframe_elem.content_frame()

            pwd_tab = frame.locator("text=密码登录")
            pwd_tab.wait_for(state="visible", timeout=5000)
            pwd_tab.click()
            time.sleep(1)

            frame.locator("#username").fill(self.account)
            time.sleep(0.3)
            frame.locator("#password").fill(self.password)
            time.sleep(0.3)
            frame.locator("#login-btn").click()
            time.sleep(5)

            body = self.page.inner_text("body")
            if any(kw in body for kw in ["虎牙号", "个人中心", "我的财产", "退出"]):
                log("SUCCESS", f"账号 [{mask_account(self.account)}] 密码登录成功！")
                cookies = self.context.cookies()
                cookie_pairs = [f"{c['name']}={c['value']}" for c in cookies if "huya.com" in c.get("domain", "")]
                self.cookie_str = "; ".join(cookie_pairs)
                save_cookie_to_files(self.cookie_str, cookies)
                return True
            else:
                log("ERROR", "登录后未检测到个人中心标识，可能触发滑块验证")
                return False
        except Exception as e:
            log("ERROR", f"登录过程异常: {e}")
            return False

    def query_badge_from_web(self) -> dict:
        """从网页 DOM 悬停勋章卡片中提取亲密度及等级数据"""
        badge_data = {
            "fans_level": "未知",
            "need_intimacy": "未知",
            "intimacy_progress": "",
            "badge_name": ""
        }
        try:
            card = self.page.locator(".chat-host-pic, #chatHostPic, [class*='FanClubHd']").first
            if card.is_visible():
                card.hover()
                time.sleep(1.5)
                panel = self.page.locator("[class*='FansCard'], [class*='fans-card'], [class*='panel-fans']").first
                if panel.is_visible():
                    txt = panel.inner_text()
                    m_lvl = re.search(r'(\d+)\s*级', txt)
                    if m_lvl:
                        badge_data["fans_level"] = f"{m_lvl.group(1)}级"
                    m_need = re.search(r'还差\s*(\d+)\s*亲密度', txt)
                    if m_need:
                        badge_data["need_intimacy"] = m_need.group(1)
                    m_prog = re.search(r'(\d+)\s*/\s*(\d+)', txt)
                    if m_prog:
                        badge_data["intimacy_progress"] = f"{m_prog.group(1)}/{m_prog.group(2)}"
        except Exception as e:
            log("DEBUG", f"网页提取勋章数据说明: {e}")
        return badge_data

    def web_punch_card(self) -> dict:
        """执行网页端鼠标悬停打卡"""
        log("INFO", f"进入直播间 [{self.room_url}] 执行网页勋章打卡...")
        result = {
            "success": False,
            "status": "未完成",
            "detail": "未完成",
            "fans_level": "",
            "need_intimacy": "",
            "intimacy_progress": ""
        }

        try:
            self.page.goto(self.room_url, wait_until="domcontentloaded")
            time.sleep(4)

            badge_elem = None
            for _ in range(10):
                elem = self.page.locator("#chatHostPic, .chat-host-pic, [class*='FanClubHd']").first
                if elem.is_visible():
                    txt = elem.inner_text().strip()
                    if txt and "成为粉丝" not in txt:
                        badge_elem = elem
                        break
                time.sleep(1)

            if not badge_elem or not badge_elem.is_visible():
                badge_elem = self.page.locator("#chatHostPic, .chat-host-pic, [class*='FanClubHd']").first

            if not badge_elem or not badge_elem.is_visible():
                log("WARN", "未找到输入框左侧粉丝勋章入口 (#chatHostPic)")
                result["detail"] = "网页端未找到粉丝勋章入口"
                return result

            badge_elem.hover()
            try:
                badge_elem.dispatch_event("mouseenter")
            except Exception:
                pass
            time.sleep(2)

            # 抓取亲密度与等级
            badge_info = self.query_badge_from_web()
            result.update(badge_info)

            task_item = self.page.locator("[class*='TaskItem']:has-text('每日打卡'), div:has-text('每日打卡领福利')").first
            if not task_item.is_visible():
                try:
                    badge_elem.click()
                except Exception:
                    pass
                time.sleep(1.5)
                task_item = self.page.locator("[class*='TaskItem']:has-text('每日打卡'), div:has-text('每日打卡领福利')").first

            if task_item.is_visible():
                task_text = task_item.inner_text().strip()
                if "已完成" in task_text or "已打卡" in task_text:
                    log("SUCCESS", "网页端检测到今日打卡已完成。")
                    result["success"] = True
                    result["status"] = "已打卡"
                    result["detail"] = "今日已完成打卡（亲密度已加）"
                else:
                    daka_btn = task_item.locator("a, button, [class*='Btn']").first
                    if daka_btn.is_visible():
                        daka_btn.click()
                        time.sleep(2)
                        log("SUCCESS", "网页端点击打卡按钮成功！")
                        result["success"] = True
                        result["status"] = "打卡成功"
                        result["detail"] = "网页端打卡成功（亲密度+5）"
            else:
                log("WARN", "未捕获到打卡任务项浮层")
                result["detail"] = "未捕获到打卡浮层"

        except Exception as e:
            log("ERROR", f"网页打卡发生异常: {e}")
            result["detail"] = f"网页打卡异常: {e}"

        return result

    def web_send_tiger_food(self) -> dict:
        """访问专属包裹页面赠送虎粮"""
        lp = self.room_info.get("lp") or "0"
        gid = self.room_info.get("gid") or "0"
        nick = self.room_info.get("nick") or "目标主播"

        result = {
            "success": False,
            "count": 0,
            "status": "未完成",
            "detail": ""
        }

        package_url = f"https://hd.huya.com/web/webPackageV2/index.html?lp={lp}&gid={gid}"
        log("INFO", f"正在打开主播 [{nick}] 专属包裹页面: {package_url}")
        self.page.goto(package_url, wait_until="domcontentloaded")
        time.sleep(3)

        try:
            self.page.wait_for_selector(".m-gift-item, :has-text('暂无包裹礼物')", timeout=10000)
        except Exception:
            pass

        body_text = self.page.inner_text("body")
        if "暂无包裹礼物" in body_text:
            log("INFO", "【包裹检查】当前包裹为空，暂无免费虎粮道具。")
            result["success"] = True
            result["count"] = 0
            result["status"] = "暂无虎粮"
            result["detail"] = "今日包裹暂无免费虎粮"
            return result

        gift_items = self.page.locator(".m-gift-item").all()
        target_card = None
        for item in gift_items:
            try:
                if "虎粮" in item.inner_text():
                    target_card = item
                    break
            except Exception:
                continue

        if not target_card:
            log("INFO", "【包裹检查】包裹中暂无【虎粮】，今日无需赠送。")
            result["success"] = True
            result["count"] = 0
            result["status"] = "暂无虎粮"
            result["detail"] = "包裹中暂无虎粮"
            return result

        count_elem = target_card.locator(".c-count")
        try:
            count_str = count_elem.inner_text().strip()
            total_count = int(re.sub(r"\D", "", count_str))
        except Exception:
            total_count = int(target_card.get_attribute("data-num") or "0")

        log("INFO", f"【包裹检查】发现虎粮道具，当前总可用库存: {total_count} 个")
        if total_count <= 0:
            result["success"] = True
            result["count"] = 0
            result["status"] = "库存为0"
            result["detail"] = "虎粮库存为 0"
            return result

        if self.gift_count and self.gift_count > 0:
            send_count = min(self.gift_count, total_count)
            count_desc = f"{send_count} 个 (上限配置: {self.gift_count})"
        else:
            send_count = total_count
            count_desc = f"{send_count} 个 (全部送出)"

        log("INFO", f"计划赠送数量: {count_desc}，当前可用库存: {total_count} 个")

        try:
            target_card.dispatch_event("mouseover")
            time.sleep(0.5)

            present_panel = self.page.locator(".g-present-content")
            present_panel.wait_for(state="visible", timeout=5000)

            input_box = present_panel.locator(".m-present-btn input[type='number'], input[placeholder*='自定义']")
            input_box.wait_for(state="visible", timeout=3000)
            input_box.click()
            input_box.fill(str(send_count))
            time.sleep(0.5)

            send_btn = present_panel.locator(".m-present-btn .c-send, :has-text('送出')").first
            send_btn.click()
            time.sleep(1)

            confirm_btn = self.page.locator("button:has-text('立即送出'), a:has-text('立即送出'), .btn-success").first
            if confirm_btn.is_visible():
                confirm_btn.click()
                time.sleep(2)

            result["success"] = True
            result["count"] = send_count
            result["left_count"] = max(0, total_count - send_count)
            result["status"] = "赠送成功"
            result["detail"] = f"成功送出 {send_count} 个免费虎粮（亲密度+{send_count}）"
            log("SUCCESS", f"🎉 {result['detail']}")
        except Exception as e:
            log("ERROR", f"送虎粮过程异常: {e}")
            result["detail"] = f"送礼异常: {e}"

        return result

    def execute(self) -> dict:
        """运行 v1 完整流程"""
        log("INFO", "========== 启动虎牙每日自动助手 v1 (网页端) ==========")
        log("INFO", f"当前执行账号: [{mask_account(self.account)}]")
        summary = {
            "version": "v1 (网页端)",
            "nick": self.room_info.get("nick") or "目标主播",
            "room_id": str(self.room_info.get("profileRoom") or "未知"),
            "account": self.account,
            "daka_success": False,
            "daka_detail": "跳过打卡",
            "gift_success": False,
            "gift_detail": "未赠送",
            "fans_level": "",
            "badge_name": "",
            "need_intimacy": "",
            "intimacy_progress": "",
            "all_success": False
        }

        try:
            logged_in = self.ensure_logged_in()
            if not logged_in:
                summary["daka_detail"] = "登录失败"
                summary["gift_detail"] = "登录失败"
            else:
                if self.do_daka:
                    daka_res = self.web_punch_card()
                    summary["daka_success"] = daka_res.get("success", False)
                    summary["daka_detail"] = daka_res.get("detail", "")
                    if daka_res.get("fans_level"):
                        summary["fans_level"] = daka_res["fans_level"]
                    if daka_res.get("badge_name"):
                        summary["badge_name"] = daka_res["badge_name"]
                    if daka_res.get("need_intimacy"):
                        summary["need_intimacy"] = daka_res["need_intimacy"]
                    if daka_res.get("intimacy_progress"):
                        summary["intimacy_progress"] = daka_res["intimacy_progress"]
                else:
                    summary["daka_success"] = True
                    summary["daka_detail"] = "配置跳过打卡"

                gift_res = self.web_send_tiger_food()
                summary["gift_success"] = gift_res.get("success", False)
                summary["gift_detail"] = gift_res.get("detail", "")
                summary["left_count"] = gift_res.get("left_count")
                summary["all_success"] = summary["daka_success"] and summary["gift_success"]
        finally:
            self._close_browser()

        if self.wechat_push:
            push_wecom_message(summary, self.config)
        else:
            log("INFO", "企业微信推送已禁用。")
        log("INFO", "========== 虎牙助手 v1 网页端运行结束 ==========")
        return summary


def run(args=None) -> dict:
    """外部总入口调用的主函数"""
    config = DEFAULT_CONFIG.copy()
    if args:
        config.update({
            "GIFT_COUNT": getattr(args, "count", config["GIFT_COUNT"]),
            "ROOM_URL": getattr(args, "room", None) or config["ROOM_URL"],
            "DO_DAKA": getattr(args, "do_daka", not getattr(args, "no_daka", False)),
            "WECHAT_PUSH": getattr(args, "wechat_push", config["WECHAT_PUSH"]),
            "HEADLESS": not getattr(args, "local_debug", getattr(args, "headful", False)),
            "ACCOUNT": getattr(args, "account", config["ACCOUNT"]),
            "PASSWORD": getattr(args, "password", config["PASSWORD"]),
            "COOKIE": getattr(args, "cookie", config["COOKIE"]),
            "COOKIE_FILE": getattr(args, "cookie_file", config["COOKIE_FILE"]),
            "WX_WEBHOOK": getattr(args, "wx_webhook", config["WX_WEBHOOK"]),
        })

    bot = HuyaWebBotV1(config)
    return bot.execute()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="虎牙每日自动助手 v1 (网页端)")
    parser.add_argument("-c", "--count", type=int, default=0, help="赠送虎粮数量 (0 为全部送出，默认 0)")
    parser.add_argument("--headful", action="store_true", help="开启浏览器可视化窗口 (默认无头后台)")
    parser.add_argument("--no-daka", action="store_true", help="跳过每日打卡")
    parser.add_argument("--room", type=str, default=None, help="目标直播间 URL")
    cli_args = parser.parse_args()

    run(cli_args)
