"""Capture polished README screenshots from the running frontend."""
from __future__ import annotations

import json
import time
from pathlib import Path

from jose import jwt
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
BASE = "http://localhost:5175"
SECRET = "change-me-in-production"

DEMO_CHAT_JS = r"""
() => {
  const root = document.querySelector('.chat-page');
  if (!root || !root.__vueParentComponent) return false;
  const proxy = root.__vueParentComponent.proxy;
  proxy.messages = [
    {
      role: 'user',
      content: '知识库支持哪些文档格式？构建完成后如何带来源问答？',
      finished: true
    },
    {
      role: 'assistant',
      content: '支持上传 MD、PDF、DOCX、TXT。构建向量索引后，用「纯 RAG」或「智能模式」提问即可；回答下方会展开参考来源，包含文件名、页码与 chunk 索引，便于核对原文。',
      finished: true,
      thoughtProcess: [
        { thought: '识别为知识库能力问题，优先检索本地文档说明。' },
        { thought: '汇总支持格式与引用来源展示逻辑，给出可执行步骤。' }
      ],
      reasoningOpen: true,
      sources: [
        {
          filename: 'demo_agentic_rag.md',
          page: 1,
          chunk_index: 2,
          preview: 'Agentic RAG 支持文档入库、混合检索、带来源回答与工具调用…'
        },
        {
          filename: 'QUICKSTART.md',
          page: 1,
          chunk_index: 0,
          preview: '上传文档并点击开始构建，然后在对话中提问…'
        }
      ]
    }
  ];
  proxy.conversationId = 'demo-readme';
  return true;
}
"""

DEMO_AGENT_JS = r"""
() => {
  const root = document.querySelector('.chat-page');
  if (!root || !root.__vueParentComponent) return false;
  const proxy = root.__vueParentComponent.proxy;
  proxy.messages = [
    {
      role: 'user',
      content: '今天北京天气怎么样？顺便总结一下知识库里 Nginx 反向代理的要点。',
      finished: true
    },
    {
      role: 'assistant',
      content: '北京今日多云转阵雨，气温约 24–31°C，湿度偏高。\\n\\n关于 Nginx 反向代理：建议用子域名分流前后端，注意 websocket / SSE 关闭缓冲，并配置 HTTPS 证书与正确的 proxy_pass。',
      finished: true,
      thoughtProcess: [
        { thought: '问题含实时天气 + 私有文档要点，计划先调用 weather 工具，再检索知识库。' },
        { thought: '工具 weather 返回北京天气；检索命中 Nginx 反向代理配置指南。' },
        { thought: '合并工具结果与文档来源，生成可核对回答。' }
      ],
      reasoningOpen: true,
      sources: [
        {
          filename: 'Nginx反向代理改子域名配置指南.md',
          page: 1,
          chunk_index: 3,
          preview: '在宝塔面板中为子域名添加反向代理，并关闭 gzip / buffering…'
        }
      ]
    }
  ];
  return true;
}
"""


def make_token() -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "admin",
            "user_id": "admin",
            "tenant_id": "default",
            "roles": ["admin"],
            "auth_type": "password",
            "exp": now + 86400,
            "iat": now,
        },
        SECRET,
        algorithm="HS256",
    )


def inject_auth(page, token: str) -> None:
    payload = json.dumps(
        {
            "accessToken": token,
            "currentUser": {
                "username": "admin",
                "user_id": "admin",
                "tenant_id": "default",
                "roles": ["admin"],
            },
        }
    )
    page.add_init_script(f"localStorage.setItem('ragAuth', {json.dumps(payload)});")


def dismiss_noise(page) -> None:
    page.evaluate(
        """() => {
          document.querySelectorAll('.el-message, .el-notification, .el-loading-mask').forEach(el => el.remove());
        }"""
    )


def shot(page, name: str, full_page: bool = True) -> None:
    dismiss_noise(page)
    page.wait_for_timeout(500)
    path = OUT / name
    page.screenshot(path=str(path), full_page=full_page)
    print(f"saved {path.name} ({path.stat().st_size} bytes)")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    token = make_token()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)

        # Login (new dark starfield UI)
        login = context.new_page()
        login.goto(f"{BASE}/login", wait_until="networkidle")
        login.wait_for_timeout(1800)
        # Force show password form even if auth disabled
        login.evaluate(
            """() => {
              const root = document.querySelector('.login-page');
              const proxy = root && root.__vueParentComponent && root.__vueParentComponent.proxy;
              if (proxy && proxy.auth) {
                proxy.auth.authStatus.enabled = true;
                proxy.auth.authStatus.password_login_enabled = true;
              }
            }"""
        )
        login.wait_for_timeout(400)
        shot(login, "login-hero.png", full_page=False)

        page = context.new_page()
        inject_auth(page, token)
        page.route(
            "**/api/auth/status",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "enabled": True,
                        "password_login_enabled": True,
                        "oidc_enabled": False,
                        "demo_users": ["admin"],
                    }
                ),
            ),
        )

        # Home hero (empty-state / ready KB)
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.wait_for_timeout(1200)
        # Ensure empty hero if garbage history auto-loaded
        page.evaluate(
            """() => {
              const root = document.querySelector('.chat-page');
              const proxy = root && root.__vueParentComponent && root.__vueParentComponent.proxy;
              if (proxy) { proxy.messages = []; proxy.conversationId = null; }
            }"""
        )
        page.wait_for_timeout(600)
        shot(page, "home-hero.png")

        # Knowledge build page — do NOT click build
        page.goto(f"{BASE}/knowledge", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.evaluate("document.querySelectorAll('.el-message').forEach(el => el.remove())")
        page.get_by_role("tab", name="上传构建").click()
        page.wait_for_timeout(700)
        shot(page, "kb-build.png")

        # File manager
        page.get_by_role("tab", name="文件管理").click()
        page.wait_for_timeout(1400)
        shot(page, "file-manager.png")

        # Chat with sources
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.wait_for_timeout(800)
        ok = page.evaluate(DEMO_CHAT_JS)
        print("inject chat:", ok)
        page.wait_for_timeout(800)
        # Expand sources collapse
        page.evaluate(
            """() => {
              const item = document.querySelector('.message-sources .el-collapse-item__header');
              if (item && item.getAttribute('aria-expanded') !== 'true') item.click();
            }"""
        )
        page.wait_for_timeout(500)
        shot(page, "chat-with-sources.png")

        # Agent mode
        ok2 = page.evaluate(DEMO_AGENT_JS)
        print("inject agent:", ok2)
        page.wait_for_timeout(500)
        page.evaluate(
            """() => {
              const item = document.querySelector('.message-sources .el-collapse-item__header');
              if (item && item.getAttribute('aria-expanded') !== 'true') item.click();
            }"""
        )
        page.wait_for_timeout(500)
        shot(page, "agent-mode.png")

        # Settings
        page.goto(f"{BASE}/settings", wait_until="networkidle")
        page.wait_for_timeout(1000)
        shot(page, "settings.png")

        browser.close()
    print("done")


if __name__ == "__main__":
    main()
