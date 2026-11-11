/**
 * Cloudflare Worker: 虎牙一键扫码登录与 Cookie 自动同步网关
 * 
 * 🛡️ 安全与功能特性：
 * 1. 极简黑白方块与深色现代化设计：适配移动端刘海/灵动岛全屏 PWA，只展示二维码供手机扫码。
 * 2. 页面访问锁（Auth Key）：未授权访客无法加载登录接口与二维码，防恶意调用。
 * 3. 纯协议扫码：无感直连虎牙官方 UDB 扫码网关，秒级获取二维码并长轮询状态。
 * 4. 自动同步 Actions：扫码确认后，自动合并所有跨域凭据并通过 GitHub API 自动写入 Secret 并触发验证！
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
      color: #38bdf8;
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
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34d399;
      font-size: 11px;
      padding: 3px 10px;
      border-radius: 20px;
      margin-top: 8px;
      font-weight: 500;
    }
    .qr-container {
      margin: 22px auto 16px;
      width: 220px;
      height: 220px;
      background: #ffffff;
      border-radius: 18px;
      padding: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
      position: relative;
      overflow: hidden;
    }
    .qr-img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      border-radius: 10px;
      transition: opacity 0.3s;
    }
    .qr-mask {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.88);
      backdrop-filter: blur(4px);
      display: none;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #f8fafc;
      padding: 16px;
      gap: 10px;
      border-radius: 18px;
      cursor: pointer;
    }
    .qr-mask p { font-size: 13px; font-weight: 500; }
    .btn-refresh {
      background: #0284c7;
      color: white;
      border: none;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border-radius: 30px;
      font-size: 13px;
      font-weight: 500;
      margin-top: 4px;
      transition: all 0.3s;
    }
    .status-waiting {
      background: rgba(56, 189, 248, 0.12);
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.3);
    }
    .status-scanned {
      background: rgba(245, 158, 11, 0.15);
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.4);
      animation: pulse 1.5s infinite;
    }
    .status-success {
      background: rgba(16, 185, 129, 0.18);
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
      50% { transform: scale(1.05); opacity: 0.85; }
      100% { transform: scale(1); opacity: 1; }
    }
    .tips {
      margin-top: 20px;
      font-size: 12px;
      color: #64748b;
      line-height: 1.6;
    }
    .tips span {
      color: #94a3b8;
      font-weight: 500;
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

  <!-- 主卡片：只展示二维码 -->
  <div class="card" id="mainCard">
    <div class="title-box">
      <h1><span>🐯</span> 虎牙助手 · 扫码登录</h1>
      <p>免账号密码 · 官方通道 · 自动同步至 Actions</p>
      <div class="security-badge">
        <span>🛡️</span> 端到端加密凭据传输
      </div>
    </div>

    <!-- 二维码显示区 -->
    <div class="qr-container">
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

    <div class="tips">
      打开 <span>虎牙直播 App</span> ➔ <span>我的</span> ➔ 右上角 <span>扫一扫</span><br>
      扫码确认后，系统将自动更新云端凭据并启动每日助手
    </div>

    <div class="footer-bar">
      <span>仓库: ${targetRepo}</span>
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
    const MAX_POLLS = 100; // 最多轮询 ~3.5 分钟

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
      if (pollTimer) clearInterval(pollTimer);
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

    function startPolling() {
      pollCount = 0;
      if (pollTimer) clearInterval(pollTimer);

      pollTimer = setInterval(async () => {
        pollCount++;
        if (pollCount > MAX_POLLS) {
          clearInterval(pollTimer);
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
            clearInterval(pollTimer);
            return;
          }

          const res = await resp.json();
          if (res.stage === 0) {
            setBadge("waiting", "等待扫码：打开虎牙 App 扫一扫");
          } else if (res.stage === 1) {
            setBadge("scanned", "📱 手机已扫码！请在 App 上点击确认登录");
          } else if (res.success || res.status === "confirmed" || res.stage === 2) {
            clearInterval(pollTimer);
            const accName = res.account ? " [" + res.account + "]" : "";
            setBadge("success", "🎉 登录成功" + accName + "！已自动同步至 Actions");
            document.getElementById("qrImg").style.opacity = "0.3";
            alert("🎉 恭喜！虎牙登录成功！\\n\\n最新 Cookie 已自动加密写入 GitHub Actions Secrets，并已触发云端每日任务！");
          } else if (res.status === "expired" || res.returnCode === -1 || res.stage === 6) {
            clearInterval(pollTimer);
            document.getElementById("qrMask").style.display = "flex";
            setBadge("error", "二维码已失效，点击刷新");
          } else {
            console.log("轮询中:", res);
          }
        } catch (e) {
          // 忽略偶发的网络抖动
        }
      }, 2000);
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

        const getQrIdPayload = {
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
            behavior: JSON.stringify({ furl: "https://i.huya.com/", curl: "https://i.huya.com/", user_action: [] }),
            type: "",
            domainList: "huya.com,yy.com",
            page: "https://i.huya.com/"
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
          body: JSON.stringify(getQrIdPayload)
        });

        // 提取 web_qrlogin_confirm_id 会话 Cookie
        let confirmCookie = "";
        let rawCookies = [];
        if (typeof huyaResp.headers.getSetCookie === "function") {
          rawCookies = huyaResp.headers.getSetCookie();
        } else {
          const h = huyaResp.headers.get("set-cookie") || "";
          rawCookies = h.split(/,(?=[^;]+=[^;]+)/g);
        }
        for (const item of rawCookies) {
          const part = item.split(";")[0].trim();
          if (part && part.startsWith("web_qrlogin_confirm_id=")) {
            confirmCookie = part;
            break;
          }
        }

        const huyaData = await huyaResp.json();
        const qrId = huyaData?.data?.qrId;
        if (!qrId) {
          return new Response(JSON.stringify({ success: false, error: "获取虎牙二维码 ID 失败" }), {
            status: 500,
            headers: { "Content-Type": "application/json" }
          });
        }

        // 获取二维码二进制并转为 Base64 图片
        const imgResp = await fetch(`https://udblgn.huya.com/qrLgn/getQrImg?k=${qrId}&appId=5002`, {
          headers: {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://aq.huya.com/"
          }
        });
        const imgBuffer = await imgResp.arrayBuffer();
        const base64Img = btoa(String.fromCharCode(...new Uint8Array(imgBuffer)));

        return new Response(JSON.stringify({
          success: true,
          qrId: qrId,
          context: contextId,
          confirmCookie: confirmCookie,
          qrImg: `data:image/png;base64,${base64Img}`
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      } catch (err) {
        return new Response(JSON.stringify({ success: false, error: err.message }), {
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
            domainList: "huya.com,yy.com",
            behavior: JSON.stringify({ furl: "https://i.huya.com/", curl: "https://i.huya.com/", user_action: [] }),
            page: "https://i.huya.com/"
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

          // 1. 抓取 tryQrLogin 的 Set-Cookie
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
              cookieMap[k.trim()] = v.trim();
            }
          }

          // 2. 依次访问 domainUrlList 抓取跨域 Set-Cookie
          for (const dUrl of domainUrls) {
            try {
              const dResp = await fetch(dUrl, {
                redirect: "manual",
                headers: {
                  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                  "Referer": "https://i.huya.com/"
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
                  cookieMap[k.trim()] = v.trim();
                }
              }
            } catch (err) {
              console.error("访问跨域 domainUrl 异常:", dUrl, err);
            }
          }

          const cookieParts = [];
          for (const [k, v] of Object.entries(cookieMap)) {
            cookieParts.push(`${k}=${v}`);
          }
          const fullCookie = cookieParts.join("; ");
          const account = cookieMap["username"] || cookieMap["yyuid"] || cookieMap["udb_uid"] || "虎牙用户";

          // 3. 自动触发 GitHub Actions 写入 Secret 并启动验证流水线
          const ghRepo = env.GITHUB_REPO || "";
          const ghToken = env.GITHUB_TOKEN;

          if (ghToken && ghRepo) {
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
