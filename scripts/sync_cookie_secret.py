# -*- coding: utf-8 -*-
"""
自动将最新虎牙 Cookie 写入 GitHub Actions Secret，并执行验证任务
"""
import os
import sys
import base64
import requests

# 保证能正确加载项目根目录模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from nacl import encoding, public
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

def update_github_secret(repo: str, token: str, secret_name: str, secret_value: str) -> bool:
    """使用 GitHub API 公钥加密自动更新 Actions Secret"""
    if not HAS_NACL:
        print("[!] 未安装 PyNaCl，尝试通过 gh CLI 更新...")
        try:
            import subprocess
            cmd = f'echo "{secret_value}" | gh secret set {secret_name} --repo {repo}'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"🎉 成功使用 gh CLI 更新 Secret [{secret_name}]！")
                return True
        except Exception as e:
            print(f"gh CLI 更新异常: {e}")
        return False

    try:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        # 1. 获取仓库公钥
        pk_url = f"https://api.github.com/repos/{repo}/actions/secrets/public-key"
        r = requests.get(pk_url, headers=headers, timeout=10)
        r.raise_for_status()
        pk_info = r.json()

        # 2. 加密 Secret 值
        public_key = public.PublicKey(pk_info["key"].encode("utf-8"), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

        # 3. 写入 Secret
        set_url = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
        payload = {
            "encrypted_value": encrypted_b64,
            "key_id": pk_info["key_id"]
        }
        r_put = requests.put(set_url, json=payload, headers=headers, timeout=10)
        r_put.raise_for_status()
        print(f"🎉 成功更新 Secret [{secret_name}] 至 GitHub 仓库 {repo}！")
        return True
    except Exception as e:
        print(f"⚠️ 更新 GitHub Secret [{secret_name}] 失败: {e}")
        return False

def main():
    new_cookie = os.environ.get('NEW_COOKIE') or os.environ.get('HUYA_COOKIE') or ''
    new_cookie = new_cookie.strip()
    if not new_cookie:
        print("❌ 未获取到 NEW_COOKIE，请检查传入参数！")
        sys.exit(1)

    print("=" * 60)
    print("🚀 开始处理虎牙最新 Cookie 凭据同步")
    print("=" * 60)

    # 简单校验核心凭据
    if "yyuid" not in new_cookie and "udb_uid" not in new_cookie:
        print("⚠️ 警告：Cookie 中未发现 yyuid/udb_uid 字段，可能不是有效的虎牙登录凭据！")

    # 更新 GitHub Actions Secret
    gh_token = os.environ.get('GH_PAT') or os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    gh_repo = os.environ.get('GH_REPO') or os.environ.get('GITHUB_REPOSITORY') or ''

    if gh_token and gh_repo:
        ok = update_github_secret(gh_repo, gh_token, "HUYA_COOKIE", new_cookie)
        if ok:
            print("✅ GitHub Actions Secret [HUYA_COOKIE] 已同步更新为最新凭据！")
        else:
            print("❌ 更新 GitHub Secret 失败，请检查 Token 权限！")
            sys.exit(1)
    else:
        print("⚠️ 未配置 GH_PAT / GITHUB_TOKEN，跳过云端 Secret 写入")

if __name__ == '__main__':
    main()
