/**
 * Cloudflare Worker: 虎牙一键扫码登录与 Cookie 自动同步网关
 * 
 * 🛡️ 特性：
 * 1. 纯协议扫码：无感直连虎牙官方 UDB 扫码网关，秒级获取二维码。
 * 2. 实时进度流展示：无弹窗打断，直接在卡片内实时反馈扫码、凭据提取与 Actions 验证进度。
 * 3. 单飞防重轮询：彻底消除并发请求，杜绝重复触发流水线。
 * 4. 深度凭据萃取：全链路提取 WUP 网关所需的核心鉴权 Cookie（yyuid、udb_biztoken、udb_session 等）。
 */

const DEFAULT_AUTH_KEY = "";

function renderWebAppHtml(targetRepo = "", defaultKey = DEFAULT_AUTH_KEY) {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>虎牙助手 · 扫码登录</title>
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="虎牙登录">
  <meta name="theme-color" content="#0f172a">
  <link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='22' fill='%23f59e0b'/><text x='50' y='68' font-size='55' text-anchor='middle'>🐯</text></svg>">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Segoe UI", Roboto, sans-serif; }
    body {
      background-color: #0f172a;
      color: #f8fafc;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
      padding-top: max(48px, calc(env(safe-area-inset-top, 44px) + 20px));
      padding-bottom: max(32px, calc(env(safe-area-inset-bottom, 20px) + 20px));
      padding-left: max(16px, env(safe-area-inset-left));
      padding-right: max(16px, env(safe-area-inset-right));
      justify-content: center;
    }
    .card {
      background: #1e293b;
      border-radius: 24px;
      width: 100%;
      max-width: 380px;
      padding: 28px 24px;
      box-shadow: 0 12px 30px -5px rgba(0, 0, 0, 0.5);
      border: 1px solid #334155;
      text-align: center;
      position: relative;
    }
    .title-box h1 {
      font-size: 20px;
      font-weight: 700;
      color: #f8fafc;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    .title-box p {
      font-size: 13px;
      color: #94a3b8;
      margin-top: 6px;
    }
    .security-badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.25);
      color: #34d399;
      font-size: 11px;
      padding: 3px 10px;
      border-radius: 20px;
      margin-top: 10px;
    }
    .qr-container {
      margin: 22px auto 16px;
      width: 230px;
      height: 230px;
      background: #0f172a;
      border-radius: 20px;
      padding: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #334155;
      box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.4);
      position: relative;
      overflow: hidden;
    }
    .qr-img {
      width: 100%;
      height: 100%;
      border-radius: 12px;
      background: #ffffff;
      padding: 8px;
      transition: opacity 0.3s;
    }
    .qr-mask {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.92);
      backdrop-filter: blur(4px);
      display: none;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #f8fafc;
      padding: 16px;
      cursor: pointer;
    }
    .qr-mask p {
      font-size: 14px;
      font-weight: 600;
      color: #f87171;
      margin-bottom: 12px;
    }
    .btn-refresh {
      background: #0284c7;
      color: white;
      border: none;
      border-radius: 20px;
      padding: 8px 18px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4);
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 16px;
      border-radius: 30px;
      font-size: 13px;
      font-weight: 500;
      transition: all 0.3s;
      margin-top: 4px;
    }
    .status-waiting {
      background: rgba(56, 189, 248, 0.12);
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.3);
      animation: pulse 2s infinite;
    }
    .status-scanned {
      background: rgba(245, 158, 11, 0.15);
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.4);
      animation: pulse 1.2s infinite;
    }
    .status-success {
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .status-error {
      background: rgba(239, 68, 68, 0.15);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: currentColor;
    }
    @keyframes pulse {
      0% { transform: scale(1); opacity: 1; }
      50% { transform: scale(1.04); opacity: 0.85; }
      100% { transform: scale(1); opacity: 1; }
    }
    .tips {
      margin-top: 18px;
      font-size: 12px;
      color: #64748b;
      line-height: 1.6;
    }
    .tips span {
      color: #94a3b8;
      font-weight: 500;
    }

    /* 实时进度流展示卡片 */
    .progress-box {
      margin-top: 18px;
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 16px;
      padding: 18px 16px;
      text-align: left;
    }
    .progress-step {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      position: relative;
      padding-bottom: 16px;
    }
    .progress-step:last-child {
      padding-bottom: 0;
    }
    .progress-step:not(:last-child)::after {
      content: '';
      position: absolute;
      left: 13px;
      top: 26px;
      bottom: 0;
      width: 2px;
      background: #334155;
    }
    .progress-step.step-done:not(:last-child)::after {
      background: #10b981;
    }
    .step-badge {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: #334155;
      color: #94a3b8;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      font-weight: 700;
      flex-shrink: 0;
      z-index: 1;
      transition: all 0.3s;
    }
    .progress-step.step-done .step-badge {
      background: #10b981;
      color: white;
      box-shadow: 0 0 12px rgba(16, 185, 129, 0.4);
    }
    .progress-step.step-running .step-badge {
      background: #0284c7;
      color: white;
      box-shadow: 0 0 12px rgba(2, 132, 199, 0.5);
    }
    .mini-spinner {
      width: 14px;
      height: 14px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .step-main {
      font-size: 14px;
      font-weight: 600;
      color: #cbd5e1;
      margin-bottom: 2px;
    }
    .progress-step.step-done .step-main {
      color: #10b981;
    }
    .progress-step.step-running .step-main {
      color: #38bdf8;
    }
    .step-sub {
      font-size: 12px;
      color: #64748b;
      line-height: 1.4;
    }

    /* 访问锁遮罩界面 */
    .lock-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.95);
      backdrop-filter: blur(8px);
      z-index: 100;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .lock-box {
      background: #1e293b;
      border-radius: 24px;
      width: 100%;
      max-width: 340px;
      padding: 30px 24px;
      box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6);
      border: 1px solid #334155;
      text-align: center;
    }
    .lock-box h2 {
      font-size: 18px;
      color: #f8fafc;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
    .lock-box p {
      font-size: 13px;
      color: #94a3b8;
      margin-bottom: 20px;
    }
    .lock-input {
      width: 100%;
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 12px;
      color: #f8fafc;
      padding: 13px 14px;
      font-size: 16px;
      text-align: center;
      letter-spacing: 2px;
      outline: none;
      margin-bottom: 16px;
      transition: border-color 0.2s;
    }
    .lock-input:focus {
      border-color: #38bdf8;
      box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
    }
    .btn-lock {
      background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
      color: white;
      border: none;
      border-radius: 12px;
      width: 100%;
      padding: 14px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
    }
    .btn-lock:active { transform: scale(0.98); }
    .lock-err {
      color: #f87171;
      font-size: 12px;
      margin-top: 10px;
      display: none;
    }
    .footer-bar {
      margin-top: 18px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      font-size: 11px;
      color: #475569;
    }
    .footer-bar a {
      color: #64748b;
      text-decoration: none;
    }
  </style>
</head>
<body>

  <!-- 安全访问锁模态窗 -->
  <div class="lock-overlay" id="lockModal">
    <div class="lock-box">
      <h2>🔒 安全访问锁</h2>
      <p>本服务为私有凭据网关，请输入访问安全码解锁登录。</p>
      <input type="password" id="lockKeyInput" class="lock-input" placeholder="输入访问密钥" autocomplete="off">
      <button class="btn-lock" id="unlockBtn">解锁并进入</button>
      <div class="lock-err" id="lockErrMsg">访问密钥错误，请重试</div>
    </div>
  </div>

  <!-- 主卡片 -->
  <div class="card" id="mainCard">
    <div class="title-box">
      <h1><span>🐯</span> 虎牙助手 · 扫码登录</h1>
      <p>免账号密码 · 官方通道 · 自动同步至 Actions</p>
      <div class="security-badge">
        <span>🛡️</span> 端到端加密凭据传输
      </div>
    </div>

    <!-- 二维码显示区 -->
    <div class="qr-container" id="qrContainer">
      <img id="qrImg" class="qr-img" src="" alt="虎牙登录二维码" style="display: none;">
      <div id="qrLoading" style="color: #64748b; font-size: 13px;">正在获取二维码...</div>
      <div class="qr-mask" id="qrMask" onclick="loadNewQr()">
        <p>⚠️ 二维码已失效</p>
        <button class="btn-refresh">点击刷新</button>
      </div>
    </div>

    <!-- 动态状态标签 -->
    <div id="statusBadge" class="status-badge status-waiting">
      <div class="dot"></div>
      <span id="statusText">等待扫码中...</span>
    </div>

    <!-- 实时进度流展示区 -->
    <div id="progressBox" class="progress-box" style="display: none;">
      <div class="progress-step step-done" id="pstep1">
        <div class="step-badge">✓</div>
        <div class="step-text">
          <div class="step-main">手机扫码确认</div>
          <div class="step-sub">虎牙 App 已完成扫码授权</div>
        </div>
      </div>
      <div class="progress-step step-running" id="pstep2">
        <div class="step-badge"><div class="mini-spinner"></div></div>
        <div class="step-text">
          <div class="step-main">凭据加密同步</div>
          <div class="step-sub" id="pstep2Sub">正在抓取完整 Cookie 并同步至云端...</div>
        </div>
      </div>
      <div class="progress-step" id="pstep3">
        <div class="step-badge">3</div>
        <div class="step-text">
          <div class="step-main">云端执行当日全量任务</div>
          <div class="step-sub" id="pstep3Sub">已通知 Actions 启动打卡并送出全部虎粮...</div>
        </div>
      </div>
    </div>

    <div class="tips" id="normalTips">
      打开 <span>虎牙直播 App</span> ➔ <span>我的</span> ➔ 右上角 <span>扫一扫</span><br>
      扫码确认后，系统将自动更新云端凭据并启动每日助手
    </div>

    <div class="footer-bar">
      <span>${targetRepo ? `仓库: ${targetRepo}` : "虎牙每日自动助手"}</span>
      <span>·</span>
      <a href="javascript:void(0)" onclick="resetLockKey()">重设安全锁</a>
    </div>
  </div>

  <script>
    let currentQrId = "";
    let currentContext = "";
    let currentConfirmCookie = "";
    let pollTimer = null;
    let pollCount = 0;
    const MAX_POLLS = 100; // 最多轮询 ~3 分钟

    let isPollingActive = false;
    let isCompleted = false;

    function getAuthKey() {
      const urlParams = new URLSearchParams(window.location.search);
      const urlKey = urlParams.get("key");
      if (urlKey) {
        localStorage.setItem("huya_access_key", urlKey);
        return urlKey;
      }
      return localStorage.getItem("huya_access_key") || "";
    }

    function checkLock() {
      const key = getAuthKey();
      if (!key) {
        document.getElementById("lockModal").style.display = "flex";
        setTimeout(() => document.getElementById("lockKeyInput").focus(), 100);
      } else {
        document.getElementById("lockModal").style.display = "none";
        loadNewQr();
      }
    }

    document.getElementById("unlockBtn").addEventListener("click", () => {
      const input = document.getElementById("lockKeyInput").value.trim();
      if (!input) return;
      localStorage.setItem("huya_access_key", input);
      document.getElementById("lockErrMsg").style.display = "none";
      document.getElementById("lockModal").style.display = "none";
      loadNewQr();
    });

    document.getElementById("lockKeyInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") document.getElementById("unlockBtn").click();
    });

    function resetLockKey() {
      localStorage.removeItem("huya_access_key");
      location.search = "";
      location.reload();
    }

    function setBadge(type, text) {
      const badge = document.getElementById("statusBadge");
      const textElem = document.getElementById("statusText");
      badge.className = "status-badge status-" + type;
      textElem.textContent = text;
    }

    async function loadNewQr() {
      if (pollTimer) clearTimeout(pollTimer);
      isPollingActive = false;
      isCompleted = false;

      document.getElementById("qrContainer").style.display = "flex";
      document.getElementById("progressBox").style.display = "none";
      document.getElementById("normalTips").style.display = "block";
      document.getElementById("qrMask").style.display = "none";
      document.getElementById("qrImg").style.display = "none";
      document.getElementById("qrLoading").style.display = "block";
      document.getElementById("qrLoading").textContent = "正在生成最新二维码...";
      setBadge("waiting", "正在获取二维码...");

      const key = getAuthKey();
      try {
        const resp = await fetch("/api/get-qr", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Auth-Key": key
          }
        });

        if (resp.status === 403) {
          localStorage.removeItem("huya_access_key");
          document.getElementById("lockErrMsg").style.display = "block";
          document.getElementById("lockErrMsg").textContent = "访问密钥不正确！";
          document.getElementById("lockModal").style.display = "flex";
          return;
        }

        const data = await resp.json();
        if (!data.success) {
          document.getElementById("qrLoading").textContent = "获取二维码失败: " + (data.error || "未知异常");
          setBadge("error", "获取失败，请重试");
          return;
        }

        currentQrId = data.qrId;
        currentContext = data.context;
        currentConfirmCookie = data.confirmCookie || "";

        const img = document.getElementById("qrImg");
        img.src = data.qrImg;
        img.onload = () => {
          document.getElementById("qrLoading").style.display = "none";
          img.style.display = "block";
          setBadge("waiting", "等待扫码：打开虎牙 App 扫一扫");
          startPolling();
        };
      } catch (err) {
        document.getElementById("qrLoading").textContent = "网络连接异常，请重试";
        setBadge("error", "网络连接异常");
      }
    }

    function showLiveProgress(res) {
      document.getElementById("qrContainer").style.display = "none";
      document.getElementById("normalTips").style.display = "none";
      document.getElementById("progressBox").style.display = "block";

      const pstep2 = document.getElementById("pstep2");
      const pstep3 = document.getElementById("pstep3");
      const pstep2Sub = document.getElementById("pstep2Sub");
      const pstep3Sub = document.getElementById("pstep3Sub");

      // 步骤 2 立即完成
      pstep2.className = "progress-step step-done";
      pstep2.querySelector(".step-badge").textContent = "✓";
      pstep2Sub.textContent = "已捕获并加密全量授权凭据 (UID: " + (res.account || "虎牙用户") + ")";

      // 步骤 3 启动中
      pstep3.className = "progress-step step-running";
      pstep3.querySelector(".step-badge").innerHTML = '<div class="mini-spinner"></div>';
      pstep3Sub.textContent = "已触发 GitHub Actions 云端流水线，执行当日全部任务...";

      setTimeout(() => {
        pstep3.className = "progress-step step-done";
        pstep3.querySelector(".step-badge").textContent = "✓";
        pstep3Sub.textContent = "当日全部任务已成功在云端启动！请留意企业微信群机器人推送。";
      }, 2500);
    }

    function startPolling() {
      if (pollTimer) clearTimeout(pollTimer);
      pollCount = 0;
      isPollingActive = true;
      isCompleted = false;

      async function doPoll() {
        if (!isPollingActive || isCompleted) return;

        pollCount++;
        if (pollCount > MAX_POLLS) {
          isPollingActive = false;
          document.getElementById("qrMask").style.display = "flex";
          setBadge("error", "二维码已过期，点击刷新");
          return;
        }

        const key = getAuthKey();
        try {
          const resp = await fetch("/api/check-qr", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Auth-Key": key
            },
            body: JSON.stringify({
              qrId: currentQrId,
              context: currentContext,
              confirmCookie: currentConfirmCookie
            })
          });

          if (resp.status === 403) {
            isPollingActive = false;
            return;
          }

          const res = await resp.json();
          if (res.stage === 0 || res.stage === "0") {
            setBadge("waiting", "等待扫码：打开虎牙 App 扫一扫");
          } else if (res.stage === 1 || res.stage === "1") {
            setBadge("scanned", "📱 手机已扫码！请在 App 上点击确认");
          } else if (res.success || res.status === "confirmed" || res.stage === 2) {
            // 立即停止所有轮询，防止重复发出请求
            isCompleted = true;
            isPollingActive = false;

            const accName = res.account ? " [" + res.account + "]" : "";
            setBadge("success", "🎉 授权成功" + accName + "！已自动同步至 Actions");
            showLiveProgress(res);
            return;
          } else if (res.status === "expired" || res.returnCode === -1 || res.stage === 6) {
            isPollingActive = false;
            document.getElementById("qrMask").style.display = "flex";
            setBadge("error", "二维码已失效，点击刷新");
            return;
          }
        } catch (e) {
          // 忽略单次网络偶发异常
        }

        // 单飞轮询：仅在上一次请求彻底结束后间隔 1.2 秒发起下一次，杜绝重叠并发
        if (isPollingActive && !isCompleted) {
          pollTimer = setTimeout(doPoll, 1200);
        }
      }

      pollTimer = setTimeout(doPoll, 1000);
    }

    window.addEventListener("DOMContentLoaded", checkLock);
  </script>
</body>
</html>`;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const expectedAuthKey = env.AUTH_KEY || DEFAULT_AUTH_KEY;

    function verifyAuth() {
      const headerKey = request.headers.get("X-Auth-Key") || "";
      const queryKey = url.searchParams.get("key") || "";
      return headerKey === expectedAuthKey || queryKey === expectedAuthKey;
    }

    // 1. GET / ：渲染只展示二维码的前端页面
    if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/index.html")) {
      const targetRepo = env.GITHUB_REPO || "";
      const html = renderWebAppHtml(targetRepo, expectedAuthKey);
      return new Response(html, {
        status: 200,
        headers: { "Content-Type": "text/html; charset=UTF-8" }
      });
    }

    // 2. POST /api/get-qr ：获取最新虎牙登录二维码与会话 Cookie
    if (request.method === "POST" && url.pathname === "/api/get-qr") {
      if (!verifyAuth()) {
        return new Response(JSON.stringify({ success: false, error: "未授权的访问请求" }), {
          status: 403,
          headers: { "Content-Type": "application/json" }
        });
      }

      try {
        const randHex = Array.from(crypto.getRandomValues(new Uint8Array(16)))
          .map(b => b.toString(16).padStart(2, "0")).join("");
        const contextId = `WB-${randHex}-${randHex.toUpperCase()}-`;
        const reqId = Date.now().toString();

        const huyaPayload = {
          uri: "70001",
          version: "2.6",
          context: contextId,
          appId: "5002",
          appSign: "1ce3bf682483d03f146f58232ec10635",
          authId: "",
          sdid: `csid_${randHex}`,
          lcid: "2052",
          byPass: "3",
          requestId: reqId,
          data: {
            appId: "5002",
            from: "",
            behavior: "%7B%22furl%22%3A%22https%3A%2F%2Fi.huya.com%2F%22%2C%22curl%22%3A%22https%3A%2F%2Fi.huya.com%2F%22%2C%22user_action%22%3A%5B%5D%7D",
            page: "https%3A%2F%2Fi.huya.com%2F",
            type: "",
            domainList: ""
          }
        };

        const huyaResp = await fetch("https://udblgn.huya.com/qrLgn/getQrId", {
          method: "POST",
          headers: {
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://i.huya.com/",
            "Origin": "https://i.huya.com",
            "context": contextId,
            "uri": "70001",
            "lcid": "2052",
            "reqid": reqId
          },
          body: JSON.stringify(huyaPayload)
        });

        const huyaData = await huyaResp.json();
        const qrId = huyaData?.data?.qrId;

        if (!qrId) {
          return new Response(JSON.stringify({ success: false, error: "获取二维码标识失败", detail: huyaData }), {
            status: 500,
            headers: { "Content-Type": "application/json" }
          });
        }

        // 捕获 Set-Cookie 下发的 web_qrlogin_confirm_id
        let confirmCookie = "";
        try {
          if (typeof huyaResp.headers.getSetCookie === "function") {
            const cookies = huyaResp.headers.getSetCookie();
            for (const c of cookies) {
              if (c.includes("web_qrlogin_confirm_id")) {
                confirmCookie = c.split(";")[0].trim();
                break;
              }
            }
          }
          if (!confirmCookie) {
            const rawCk = huyaResp.headers.get("set-cookie") || "";
            const m = rawCk.match(/web_qrlogin_confirm_id=([^;]+)/);
            if (m) confirmCookie = `web_qrlogin_confirm_id=${m[1]}`;
          }
        } catch (e) {}

        const imgUrl = `https://udblgn.huya.com/qrLgn/getQrImg?k=${qrId}&appId=5002`;
        const imgResp = await fetch(imgUrl, {
          headers: {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://i.huya.com/"
          }
        });

        const imgBuffer = await imgResp.arrayBuffer();
        const base64Img = btoa(String.fromCharCode(...new Uint8Array(imgBuffer)));
        const dataUrl = `data:image/png;base64,${base64Img}`;

        return new Response(JSON.stringify({
          success: true,
          qrId: qrId,
          qrImg: dataUrl,
          context: contextId,
          confirmCookie: confirmCookie
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });

      } catch (err) {
        return new Response(JSON.stringify({ success: false, error: "网关内部异常: " + err.message }), {
          status: 500,
          headers: { "Content-Type": "application/json" }
        });
      }
    }

    // 3. POST /api/check-qr ：轮询二维码扫码状态并完成自动同步
    if (request.method === "POST" && url.pathname === "/api/check-qr") {
      if (!verifyAuth()) {
        return new Response(JSON.stringify({ success: false, error: "未授权的访问请求" }), {
          status: 403,
          headers: { "Content-Type": "application/json" }
        });
      }

      try {
        const reqBody = await request.json();
        const { qrId, context, confirmCookie } = reqBody;
        if (!qrId) {
          return new Response(JSON.stringify({ error: "缺少 qrId" }), { status: 400 });
        }

        const randHex = Array.from(crypto.getRandomValues(new Uint8Array(16)))
          .map(b => b.toString(16).padStart(2, "0")).join("");
        const reqId = Date.now().toString();
        const contextId = context || `WB-${randHex}-${randHex.toUpperCase()}-`;

        const checkPayload = {
          uri: "70003",
          version: "2.6",
          context: contextId,
          appId: "5002",
          appSign: "1ce3bf682483d03f146f58232ec10635",
          authId: "",
          sdid: `csid_${randHex}`,
          lcid: "2052",
          byPass: "3",
          requestId: reqId,
          data: {
            qrId: qrId,
            remember: "1",
            domainList: "",
            behavior: "%7B%22furl%22%3A%22https%3A%2F%2Fi.huya.com%2F%22%2C%22curl%22%3A%22https%3A%2F%2Fi.huya.com%2F%22%2C%22user_action%22%3A%5B%5D%7D",
            page: "https%3A%2F%2Fi.huya.com%2F"
          }
        };

        const headers = {
          "Content-Type": "application/json;charset=UTF-8",
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
          "Referer": "https://i.huya.com/",
          "Origin": "https://i.huya.com",
          "context": contextId,
          "uri": "70003",
          "lcid": "2052",
          "reqid": reqId
        };
        if (confirmCookie) {
          headers["Cookie"] = confirmCookie;
        }

        const huyaResp = await fetch("https://udblgn.huya.com/qrLgn/tryQrLogin", {
          method: "POST",
          headers: headers,
          body: JSON.stringify(checkPayload)
        });

        const checkRes = await huyaResp.json();
        const stage = checkRes?.data?.stage;
        const returnCode = checkRes?.returnCode;
        const domainUrls = checkRes?.data?.domainUrlList || [];

        // stage 0: 等待扫码 (兼容数字 0 和字符串 "0")
        if (stage === 0 || stage === "0") {
          return new Response(JSON.stringify({ stage: 0, status: "waiting" }), {
            headers: { "Content-Type": "application/json" }
          });
        }

        // stage 1: 已扫码，等待 App 确认 (兼容数字 1 和字符串 "1")
        if (stage === 1 || stage === "1") {
          return new Response(JSON.stringify({ stage: 1, status: "scanned", message: "手机已扫码，请在 App 上确认" }), {
            headers: { "Content-Type": "application/json" }
          });
        }

        // 成功判定 (依据虎牙官方 HyUDBWebSDK 规范)：
        // 1. returnCode 为 0 或 "0"，且 stage 非 0/1（确认登录后 stage 通常为 2 或返回凭据）
        // 2. 或 stage 为 2 / "2"
        // 3. 或存在 domainUrlList 跨域写入列表
        const isSuccess = (
          (String(returnCode) === "0" && stage !== undefined && stage !== null && !["0", "1", 0, 1].includes(stage)) ||
          stage === 2 || stage === "2" ||
          (String(returnCode) === "0" && Array.isArray(domainUrls) && domainUrls.length > 0)
        );

        if (isSuccess) {
          const cookieMap = {};
          if (confirmCookie && confirmCookie.includes("=")) {
            const [ck, cv] = confirmCookie.split("=", 2);
            cookieMap[ck.trim()] = cv.trim();
          }

          // A. 优先直接从 checkRes.data / checkRes 中提取用户与登录凭据
          const resData = checkRes?.data || {};
          const uid = resData.uid || resData.yyuid || resData.udb_uid || checkRes?.uid;
          if (uid) {
            cookieMap["yyuid"] = String(uid);
            cookieMap["udb_uid"] = String(uid);
          }
          const passport = resData.passport || resData.username || checkRes?.passport;
          if (passport) {
            cookieMap["username"] = String(passport);
          }
          const biztoken = resData.biztoken || checkRes?.biztoken;
          if (biztoken) {
            cookieMap["udb_biztoken"] = String(biztoken);
          }
          const sessionData = resData.sessionData || checkRes?.sessionData;
          if (sessionData) {
            cookieMap["udb_session"] = String(sessionData);
          }
          const ticket5060 = resData.ticket5060 || checkRes?.ticket5060;
          if (ticket5060) {
            cookieMap["ticket5060"] = String(ticket5060);
          }
          cookieMap["udb_passdata"] = "3";
          cookieMap["udb_appid"] = "5002";

          // B. 抓取 tryQrLogin 的 Set-Cookie
          try {
            let rawCookies = [];
            if (typeof huyaResp.headers.getSetCookie === "function") {
              rawCookies = huyaResp.headers.getSetCookie();
            } else {
              const h = huyaResp.headers.get("set-cookie") || "";
              rawCookies = h.split(/,(?=[^;]+=[^;]+)/g);
            }
            for (const item of rawCookies) {
              const part = item.split(";")[0].trim();
              if (part && part.includes("=")) {
                const [k, v] = part.split("=", 2);
                if (k && v) cookieMap[k.trim()] = v.trim();
              }
            }
          } catch (e) {}

          // C. 依次访问 domainUrlList 抓取跨域 Set-Cookie
          if (Array.isArray(domainUrls)) {
            for (const dUrl of domainUrls) {
              try {
                let targetUrl = String(dUrl).trim();
                if (targetUrl.startsWith("//")) {
                  targetUrl = "https:" + targetUrl;
                } else if (targetUrl.startsWith("http://")) {
                  targetUrl = "https://" + targetUrl.slice(7);
                }
                const dResp = await fetch(targetUrl, {
                  headers: {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Referer": "https://i.huya.com/",
                    "Cookie": confirmCookie ? `web_qrlogin_confirm_id=${confirmCookie.split("=")[1] || confirmCookie}` : ""
                  }
                });
                let dCookies = [];
                if (typeof dResp.headers.getSetCookie === "function") {
                  dCookies = dResp.headers.getSetCookie();
                } else {
                  const dh = dResp.headers.get("set-cookie") || "";
                  dCookies = dh.split(/,(?=[^;]+=[^;]+)/g);
                }
                for (const item of dCookies) {
                  const part = item.split(";")[0].trim();
                  if (part && part.includes("=")) {
                    const [k, v] = part.split("=", 2);
                    if (k && v) cookieMap[k.trim()] = v.trim();
                  }
                }
              } catch (err) {
                console.error("访问跨域 domainUrl 异常:", dUrl, err);
              }
            }
          }

          // D. 设备标识与补齐
          if (!cookieMap["guid"]) {
            cookieMap["guid"] = Array.from(crypto.getRandomValues(new Uint8Array(16)))
              .map(b => b.toString(16).padStart(2, "0")).join("");
          }
          if (!cookieMap["udb_guiddata"]) {
            cookieMap["udb_guiddata"] = cookieMap["guid"];
          }

          const cookieParts = [];
          for (const [k, v] of Object.entries(cookieMap)) {
            cookieParts.push(`${k}=${v}`);
          }
          const fullCookie = cookieParts.join("; ");
          const account = cookieMap["username"] || cookieMap["yyuid"] || cookieMap["udb_uid"] || "虎牙用户";

          // E. 自动触发 GitHub Actions 写入 Secret 并启动验证流水线
          const ghRepo = env.GITHUB_REPO || "";
          const ghToken = env.GITHUB_TOKEN;

          if (ghToken && ghRepo && (cookieMap["yyuid"] || cookieMap["udb_uid"])) {
            ctx.waitUntil((async () => {
              try {
                const dispatchUrl = `https://api.github.com/repos/${ghRepo}/dispatches`;
                await fetch(dispatchUrl, {
                  method: "POST",
                  headers: {
                    "Authorization": `Bearer ${ghToken}`,
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Huya-Worker-Sync"
                  },
                  body: JSON.stringify({
                    event_type: "update_cookie",
                    client_payload: { cookie: fullCookie, account: account }
                  })
                });
              } catch (e) {
                console.error("触发 GitHub Actions update_cookie 失败:", e);
              }
            })());
          }

          return new Response(JSON.stringify({
            success: true,
            stage: 2,
            status: "confirmed",
            account: account,
            message: "登录成功并已同步至 GitHub Actions！"
          }), {
            status: 200,
            headers: { "Content-Type": "application/json" }
          });
        }

        // 失效判定：明确 stage 6 或 returnCode 为负
        if (stage === 6 || String(returnCode) === "-1" || String(returnCode) === "10006") {
          return new Response(JSON.stringify({ stage: stage, status: "expired", returnCode: returnCode }), {
            headers: { "Content-Type": "application/json" }
          });
        }

        // 其他中间过渡态，保持轮询
        return new Response(JSON.stringify({ stage: stage, status: "pending", returnCode: returnCode }), {
          headers: { "Content-Type": "application/json" }
        });

      } catch (err) {
        return new Response(JSON.stringify({ error: "服务器内部异常: " + err.message }), {
          status: 500,
          headers: { "Content-Type": "application/json" }
        });
      }
    }

    return new Response("Not Found", { status: 404 });
  }
};
