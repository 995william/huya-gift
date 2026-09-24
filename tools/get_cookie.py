#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虎牙 Cookie 快速获取助手
本地运行此脚本将弹出浏览器，登录后自动提取并保存完整的 Cookie。
获取的 Cookie 可直接配置到 GitHub Secrets 中用于每日自动运行。
"""

import os
import sys
import time
import json
from playwright.sync_api import sync_playwright

DEFAULT_ACCOUNT = os.getenv("HUYA_ACCOUNT", "").strip()
DEFAULT_PASSWORD = os.getenv("HUYA_PASSWORD", "").strip()


def get_cookie():
    print("=" * 60)
    print("            虎牙 Cookie 获取助手            ")
    print("=" * 60)
    print("即将启动浏览器，您可以：")
    print("1. 使用虎牙 APP 扫码登录")
    print("2. 或直接输入账号密码/短信验证码登录")
    print("登录成功后，脚本会自动检测并提取 Cookie！\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("[1/3] 正在打开虎牙个人中心...")
        page.goto("https://i.huya.com/")

        # 尝试自动切换到密码登录并预填账号密码
        try:
            iframe_elem = page.wait_for_selector("#UDBSdkLgn_iframe", timeout=8000)
            if iframe_elem:
                frame = iframe_elem.content_frame()
                pwd_tab = frame.locator("text=密码登录")
                if pwd_tab.is_visible():
                    pwd_tab.click()
                    time.sleep(0.5)
                    if DEFAULT_ACCOUNT:
                        frame.locator("#username").fill(DEFAULT_ACCOUNT)
                    if DEFAULT_PASSWORD:
                        frame.locator("#password").fill(DEFAULT_PASSWORD)
                    print(f"[提示] 已预填账号 [{DEFAULT_ACCOUNT}]，请在弹出窗口中点击登录（如有滑块请拖动）。")
        except Exception:
            pass

        print("[2/3] 等待登录完成（最长等待 300 秒）...")
        logged_in = False
        start_time = time.time()

        while time.time() - start_time < 300:
            time.sleep(2)
            cookies = context.cookies()
            huya_cookies = [c for c in cookies if "huya.com" in c.get("domain", "")]
            cookie_names = [c["name"] for c in huya_cookies]

            # 检测关键登录态 Cookie
            if any(k in cookie_names for k in ["yyuid", "udb_uid", "udb_biztoken", "udb_passdata"]):
                # 再次确认页面已进入个人中心或头部已登录
                try:
                    body_text = page.inner_text("body")
                    if any(kw in body_text for kw in ["虎牙号", "个人中心", "我的财产", "退出"]):
                        logged_in = True
                        break
                except Exception:
                    pass

        if not logged_in:
            print("[错误] 登录超时或未完成登录！")
            browser.close()
            return False

        print("\n[3/3] 检测到登录成功！正在提取并保存 Cookie...")
        cookies = context.cookies()
        huya_cookies = [c for c in cookies if "huya.com" in c.get("domain", "")]
        cookie_pairs = [f"{c['name']}={c['value']}" for c in huya_cookies]
        cookie_string = "; ".join(cookie_pairs)

        # 保存为文本文件
        with open("huya_cookie.txt", "w", encoding="utf-8") as f:
            f.write(cookie_string)

        # 保存为 JSON 文件
        with open("huya_cookies.json", "w", encoding="utf-8") as f:
            json.dump(huya_cookies, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 70)
        print("🎉 恭喜！虎牙 Cookie 提取成功！")
        print("本地保存位置: huya_cookie.txt & huya_cookies.json")
        print("=" * 70)
        print("\n【GitHub Actions 配置指南】：")
        print("1. 进入您的 GitHub 项目仓库")
        print("2. 点击 Settings -> Secrets and variables -> Actions")
        print("3. 点击 'New repository secret'")
        print("4. Name 填写: HUYA_COOKIE")
        print("5. 从本地 huya_cookie.txt 读取内容并保存为 Secret（不要提交该文件）")
        print("配置完成后，GitHub Actions 即可每天免密全自动运行！\n")

        browser.close()
        return True


if __name__ == "__main__":
    success = get_cookie()
    sys.exit(0 if success else 1)
