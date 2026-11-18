# -*- coding: utf-8 -*-
"""
William 签到与自动化管控中枢 · 标准化零依赖上报 SDK (hub_reporter.py)
自动兼容 Python 3.8+ 标准库 urllib，无需额外安装任何第三方依赖。
通过环境变量读取：
  - CHECKIN_HUB_URL   (默认 https://checkin.wwcoder.top)
  - CHECKIN_HUB_TOKEN (必填，管控中枢高熵鉴权令牌)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


def report_to_hub(
    project_slug: str,
    status: str,
    summary: str = "",
    *,
    duration_ms: int = 0,
    asset_text: str = "",
    reward_total: Optional[float] = None,
    balance_total: Optional[float] = None,
    cookie_ttl_hours: Optional[float] = None,
    raw_card: str = "",
    accounts: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """
    向集中管控中枢上报本次签到或自动化任务的标准化结果。
    status 取值: 'success' | 'already_signed' | 'partial' | 'failed'
    """
    token = os.getenv("CHECKIN_HUB_TOKEN", "").strip()
    if not token:
        print("[Hub] 未配置 CHECKIN_HUB_TOKEN，跳过中枢数据上报")
        return False

    base_url = os.getenv("CHECKIN_HUB_URL", "https://checkin.wwcoder.top").strip().rstrip("/")
    endpoint = f"{base_url}/api/v1/report"

    gh_run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    gh_repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    gh_server = os.getenv("GITHUB_SERVER_URL", "https://github.com").strip().rstrip("/")
    gh_run_url = f"{gh_server}/{gh_repo}/actions/runs/{gh_run_id}" if (gh_run_id and gh_repo) else ""

    payload: Dict[str, Any] = {
        "project_slug": project_slug,
        "status": status,
        "trigger_source": "push",
        "duration_ms": max(0, int(duration_ms)),
        "summary": summary,
        "asset_text": asset_text,
        "reward_total": reward_total,
        "balance_total": balance_total,
        "cookie_ttl_hours": cookie_ttl_hours,
        "raw_card": raw_card,
        "gh_run_id": gh_run_id,
        "gh_run_url": gh_run_url,
        "accounts": accounts or [],
    }

    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-Hub-Token": token,
        "Connection": "close",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
    }

    for attempt in range(1, 3):
        try:
            req = urllib.request.Request(endpoint, data=body_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode("utf-8", errors="replace"))
                if resp.status == 200 and resp_data.get("ok"):
                    print(f"[Hub] 已成功同步记录至管控中枢 (流水号 #{resp_data.get('log_id')})")
                    return True
                print(f"[Hub] 中枢返回非预期状态: {resp.status} {resp_data}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")[:200]
            print(f"[Hub] 上报 HTTP 异常 (第 {attempt} 次): {e.code} {err_body}")
        except Exception as e:
            print(f"[Hub] 上报网络异常 (第 {attempt} 次): {e}")

    return False
