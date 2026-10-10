#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
channels-watch — 微信视频号私信「只读监控」

用途：
    监控视频号助手（channels.weixin.qq.com）的私信页，发现「打招呼消息」或「私信」
    有新内容时，通过飞书 / ntfy / Server酱 推送到手机。

设计原则（保守）：
    只读 —— 只切换「打招呼消息 / 私信」两个列表页，不点进会话、不发送任何消息；
    低频 —— 默认 5 分钟检查一次；
    本地 —— 登录态保存在本地 profile 目录，消息内容只在本机处理。

用法：
    python3 watch.py --login    首次登录：打开浏览器，扫码登录视频号助手
    python3 watch.py --check    检查登录状态与页面结构（不发推送）
    python3 watch.py --once     执行一次监控检查（默认模式）
    python3 watch.py --loop     常驻循环，按 config.json 的间隔执行
    python3 watch.py --dump     调试：输出页面结构与截图（页面改版时用）
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
STATE_FILE = BASE_DIR / "state.json"
LOG_DIR = BASE_DIR / "logs"
PROFILE_DIR = BASE_DIR / "profile"
LOCK_FILE = BASE_DIR / ".watch.lock"

PRIVATE_MSG_URL = "https://channels.weixin.qq.com/platform/private_msg"
TABS = (("greeting", "打招呼消息"), ("private", "私信"))

# 登录态被服务端吊销后，登录页会先尝试「记住账号快速登录」（显示上次账号 +
# 「登录中...」），通常 10~15 秒内自动完成、无需扫码。落在登录页时先宽限等待
# 这么长时间，等不到才判定真·未登录（2026-10-09 实测：曾因固定 6 秒就检查，
# 把快速登录过程误报成了「登录失效」）。
QUICK_LOGIN_GRACE_SECONDS = 40

# 2026-10-10 事故：微信 4.x 桌面端需真人在「视频号创作平台 申请使用」弹窗点
# 「允许」才完成快捷登录，只等 is_login_page 翻转永远无法自愈。落在登录页时
# 点击 iframe 里的「微信快捷登录」发起请求，并在下列窗口内保持浏览器与请求
# 存活、定期重发请求（微信弹窗超时可再次请求），等人工确认后自动完成登录。
QUICK_LOGIN_CONFIRM_SECONDS = 300
QUICK_LOGIN_RECLICK_SECONDS = 90

DEFAULT_CONFIG = {
    "push": {
        "channel": "feishu",  # feishu | ntfy | serverchan
        "feishu_webhook": "",
        "ntfy": {"server": "https://ntfy.sh", "topic": ""},
        "serverchan_key": "",
    },
    "interval_seconds": 300,
    "headless": True,
    "tabs": {"greeting": True, "private": True},
}

# 会话条目的「时间文案」会造成误报，做规范化时剔除
TIME_NOISE_RE = re.compile(
    r"(刚刚|昨天|前天|\d+\s*(秒|分钟|小时|天|周|个月|年)前|\d{1,2}:\d{2}|"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2})"
)

# 私信页内容在 wujie 微前端的 shadow DOM 里，普通 JS（querySelectorAll）
# 抓不到；Playwright 的 locator 能自动穿透 open shadow DOM，全用它。
SESSION_SELECTOR = ".session-wrap"


# ---------------------------------------------------------------- 基础工具

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    line = f"[{now_str()}] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(exist_ok=True)
        path = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_json(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            log(f"读取 {path.name} 失败：{exc}，使用默认值")
    return default


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    user_cfg = load_json(CONFIG_FILE, {})
    for k, v in user_cfg.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def acquire_lock():
    """获取互斥锁；已有实例在运行时返回 None（防止定时任务与手动运行撞车）。"""
    fh = LOCK_FILE.open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        return None


# ---------------------------------------------------------------- 推送

def http_post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 15) -> str:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def send_push(cfg: dict, title: str, body: str) -> bool:
    push = cfg.get("push", {})
    channel = push.get("channel", "")
    try:
        if channel == "feishu":
            webhook = push.get("feishu_webhook", "").strip()
            if not webhook:
                log("推送跳过：未配置 feishu_webhook")
                return False
            resp = http_post_json(webhook, {
                "msg_type": "text",
                "content": {"text": f"{title}\n{body}"},
            })
            log(f"飞书推送完成：{resp[:120]}")
            return True

        if channel == "ntfy":
            ntfy = push.get("ntfy", {})
            server = ntfy.get("server", "https://ntfy.sh").rstrip("/")
            topic = ntfy.get("topic", "").strip()
            if not topic:
                log("推送跳过：未配置 ntfy topic")
                return False
            data = f"{title}\n{body}".encode("utf-8")
            req = urllib.request.Request(f"{server}/{topic}", data=data, method="POST")
            req.add_header("Title", title)
            req.add_header("Tags", "bell")
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            log(f"ntfy 推送完成（{server}/{topic}）")
            return True

        if channel == "serverchan":
            key = push.get("serverchan_key", "").strip()
            if not key:
                log("推送跳过：未配置 serverchan_key")
                return False
            resp = http_post_json(
                f"https://sctapi.ftqq.com/{key}.send",
                {"title": title, "desp": body},
            )
            log(f"Server酱推送完成：{resp[:120]}")
            return True

        log(f"推送跳过：未知通道 {channel!r}")
        return False
    except urllib.error.HTTPError as exc:
        log(f"推送失败（HTTP {exc.code}）：{exc.read().decode('utf-8', 'ignore')[:200]}")
    except Exception as exc:
        log(f"推送失败：{exc}")
    return False


# ---------------------------------------------------------------- 快照与比对

def clean_text(text: str) -> str:
    return TIME_NOISE_RE.sub("", text).strip()


def sig_of(text: str) -> str:
    return hashlib.md5(clean_text(text).encode("utf-8")).hexdigest()[:12]


def detect_changes(old_items: list[dict], new_items: list[dict]) -> list[dict]:
    """对比两次快照，返回变化列表。"""
    old_map = {sig_of(x["text"]): x for x in old_items}
    changes = []
    for item in new_items:
        sig = sig_of(item["text"])
        old = old_map.get(sig)
        if old is None:
            changes.append({"kind": "new", "item": item})
        elif item.get("unread") and not old.get("unread"):
            changes.append({"kind": "unread", "item": item})
    return changes


def brief(text: str, limit: int = 60) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= limit else t[:limit] + "…"


# ---------------------------------------------------------------- 浏览器

def is_login_page(page) -> bool:
    url = (page.url or "").lower()
    if "login" in url or "passport" in url:
        return True
    try:
        text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        return False
    return ("扫码登录" in text) or ("二维码登录" in text) or ("微信扫一扫" in text)


def find_in_frames(page, text: str):
    """在页面所有 frame（含 iframe）里找可见的文本元素；找不到返回 None。

    Playwright 的 locator 穿透 shadow DOM、但不穿透 iframe，所以需要遍历
    page.frames 再查找（2026-10-10 事故：登录面板渲染在 open.weixin.qq.com
    的 qrconnect iframe 内）。
    """
    for frame in page.frames:
        try:
            loc = frame.get_by_text(text, exact=True)
            for i in range(min(loc.count(), 6)):
                el = loc.nth(i)
                try:
                    if el.is_visible():
                        return el
                except Exception:
                    continue
        except Exception:
            continue
    return None


def click_quick_login(page) -> bool:
    """点击登录面板里的「微信快捷登录」按钮（在 iframe 内，且初始可能 disabled）。

    点击后本机微信会弹「视频号创作平台 申请使用」确认框，真人点「允许」后
    登录自动完成。返回是否成功点击。
    """
    el = find_in_frames(page, "微信快捷登录")
    if el is None:
        return False
    try:
        el.click(timeout=15000)  # Playwright 会等它 visible/enabled
        return True
    except Exception as exc:
        log(f"点击「微信快捷登录」失败：{exc}")
        return False


def goto_private_msg(page, on_login_page=None) -> bool:
    """进入视频号助手的「私信管理」页。

    注意：直接 goto /platform/private_msg 会被重定向回 /platform 首页，
    需要先加载主应用，再点击侧边菜单「私信」。

    登录态被吊销后的恢复分两层：
    1. 登录页先尝试「记住账号快速登录」，通常 10~15 秒内自动完成、无需扫码——
       落在登录页时先宽限等待（QUICK_LOGIN_GRACE_SECONDS）。
    2. 2026-10-10 事故起：微信 4.x 桌面端需真人在「视频号创作平台 申请使用」
       弹窗点「允许」才完成快捷登录——宽限未完成时点击 iframe 里的「微信快捷
       登录」发起请求，并保持浏览器存活、定期重发请求，等人工确认。

    on_login_page: 自动恢复未完成时回调（用于第一时间发告警，不等恢复窗口结束）。
    """
    page.goto("https://channels.weixin.qq.com/platform", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    if is_login_page(page):
        deadline = time.time() + QUICK_LOGIN_GRACE_SECONDS
        while time.time() < deadline and is_login_page(page):
            page.wait_for_timeout(2000)
        if is_login_page(page):
            clicked = click_quick_login(page)
            if on_login_page is not None:
                try:
                    on_login_page()
                except Exception as exc:
                    log(f"登录告警回调失败：{exc}")
            if clicked:
                log("已请求微信快捷登录——请在微信弹窗点「允许」以恢复登录。")
                last_click = time.time()
                confirm_deadline = time.time() + QUICK_LOGIN_CONFIRM_SECONDS
                while time.time() < confirm_deadline and is_login_page(page):
                    now = time.time()
                    if now - last_click >= QUICK_LOGIN_RECLICK_SECONDS:
                        if click_quick_login(page):
                            last_click = now
                    page.wait_for_timeout(2000)
        if is_login_page(page):
            return False  # 恢复窗口内未完成，判定为真·未登录
        page.wait_for_timeout(4000)  # 快速登录已完成，等首页应用加载
    if "private_msg" in (page.url or ""):
        page.wait_for_timeout(2000)
        return True
    ok = False
    try:
        ok = page.evaluate(
            """() => {
                const spans = Array.from(document.querySelectorAll('span.finder-ui-desktop-menu__name'))
                    .filter(s => s.textContent.trim() === '私信');
                if (!spans.length) return false;
                const a = spans[0].closest('a');
                if (!a) return false;
                a.click();
                return true;
            }"""
        )
    except Exception as exc:
        log(f"点击「私信」菜单失败：{exc}")
        return False
    if not ok:
        return False
    try:
        page.wait_for_url("**/private_msg", timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(3000)
    return "private_msg" in (page.url or "")


def collect_snapshot(page, tab_label: str) -> dict:
    """切换到指定 tab，抓取会话列表（locator 自动穿透 shadow DOM）。"""
    clicked = False
    try:
        loc = page.get_by_text(tab_label, exact=True)
        count = loc.count()
        for i in range(min(count, 6)):
            el = loc.nth(i)
            try:
                if el.is_visible():
                    el.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue
    except Exception:
        pass
    if not clicked:
        log(f"未找到 tab「{tab_label}」的可点击元素")
    page.wait_for_timeout(1800)

    items: list[dict] = []
    try:
        wraps = page.locator(SESSION_SELECTOR)
        n = wraps.count()
        for i in range(n):
            el = wraps.nth(i)
            try:
                text = el.inner_text()
            except Exception:
                continue
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                continue
            unread = False
            for sel in (".dot", "[class*='dot']", "[class*='unread']", "[class*='badge']"):
                try:
                    if el.locator(sel).count() > 0:
                        unread = True
                        break
                except Exception:
                    continue
            items.append({"text": text[:200], "unread": unread})
    except Exception as exc:
        log(f"抓取会话失败：{exc}")
    return {"selector": SESSION_SELECTOR, "count": len(items), "items": items}


def open_context(playwright, headless: bool):
    """启动 Chrome 持久化上下文；失败（如启动超时）时记日志并重试一次。"""
    last_exc = None
    for attempt in (1, 2):
        try:
            return playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                channel="chrome",
                headless=headless,
                viewport={"width": 1440, "height": 900},
                args=[
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
        except Exception as exc:
            last_exc = exc
            log(f"Chrome 启动失败（第 {attempt} 次）：{exc}")
            if attempt == 1:
                time.sleep(5)
    raise RuntimeError(f"Chrome 启动失败：{last_exc}") from last_exc


# ---------------------------------------------------------------- 主逻辑

def cmd_login(cfg: dict) -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = open_context(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(PRIVATE_MSG_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        if is_login_page(page):
            # 先等「记住账号快速登录」走完（通常 10~15 秒），别急着让用户扫码
            deadline = time.time() + QUICK_LOGIN_GRACE_SECONDS
            while time.time() < deadline and is_login_page(page):
                page.wait_for_timeout(2000)
        if not is_login_page(page):
            log("已是登录状态（快速登录已完成），无需重新扫码。")
            ctx.close()
            return 0
        print("\n>>> 请在弹出的浏览器窗口里，用「绑定视频号的微信」扫码登录。")
        print(">>> 登录成功后将自动继续（最长等待 5 分钟）。\n")
        deadline = time.time() + 300
        logged_in = False
        while time.time() < deadline:
            page.wait_for_timeout(4000)
            if not is_login_page(page):
                page.wait_for_timeout(2000)  # 双检：避开页面导航瞬间的误判
                if not is_login_page(page):
                    logged_in = True
                    break
        if logged_in:
            log("登录成功，登录态已保存到 profile/ 目录。")
        else:
            log("等待超时，未完成登录。可重新运行 --login。")
        ctx.close()
        return 0 if logged_in else 1


def cmd_check(cfg: dict) -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = open_context(p, headless=cfg.get("headless", True))
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        ok = goto_private_msg(page)
        if not ok:
            if is_login_page(page):
                log("检查结果：未登录（请先运行 --login 扫码登录）。")
            else:
                log("检查结果：进入私信页失败（页面可能改版，可用 --dump 排查）。")
            ctx.close()
            return 2
        log("检查结果：已登录，已进入私信页。")
        for key, label in TABS:
            snap = collect_snapshot(page, label)
            log(f"tab「{label}」：选择器 {snap['selector']}，抓到 {snap['count']} 条会话")
            for it in snap["items"][:3]:
                log(f"    - {brief(it['text'])} | unread={it['unread']}")
        ctx.close()
        return 0


def cmd_dump(cfg: dict) -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = open_context(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if not goto_private_msg(page):
            if is_login_page(page):
                log("当前未登录，无法 dump。请先 --login。")
            else:
                log("未能进入私信页。")
            ctx.close()
            return 2
        LOG_DIR.mkdir(exist_ok=True)
        shot = LOG_DIR / f"dump-{datetime.now().strftime('%H%M%S')}.png"
        page.screenshot(path=str(shot), full_page=False)
        log(f"截图已保存：{shot}")
        for sel in (".session-wrap", ".main-body", ".route-name"):
            try:
                n = page.locator(sel).count()
            except Exception:
                n = -1
            log(f"选择器 {sel}: {n} 个元素")
        for key, label in TABS:
            snap = collect_snapshot(page, label)
            log(f"tab「{label}」selector={snap['selector']} count={snap['count']}")
            for it in snap["items"][:5]:
                log(f"    样例：{brief(it['text'], 80)} | unread={it['unread']}")
        ctx.close()
        return 0


def run_once(cfg: dict, do_push: bool = True) -> int:
    from playwright.sync_api import sync_playwright

    state = load_json(STATE_FILE, {"tabs": {}, "last_login_alert": ""})
    headless = cfg.get("headless", True)

    def alert_login_failure() -> None:
        """自动恢复未完成时立即告警（按日去重）。"""
        log("未登录：登录态可能已失效。")
        if not do_push:
            return
        last_alert = state.get("last_login_alert", "")
        today = datetime.now().strftime("%Y-%m-%d")
        if last_alert.startswith(today):
            return
        send_push(
            cfg,
            "视频号监控：登录失效",
            "视频号助手登录态已失效，请在 Mac 上处理：\n"
            "1. 若屏幕出现微信「视频号创作平台 申请使用」确认框，点「允许」即可自动恢复（监控会自动重试）；\n"
            f"2. 需要手动登录时（在运行副本目录执行）：cd {BASE_DIR} && python3 watch.py --login",
        )
        state["last_login_alert"] = now_str()
        save_json(STATE_FILE, state)

    with sync_playwright() as p:
        try:
            ctx = open_context(p, headless=headless)
        except Exception as exc:
            log(f"浏览器启动失败，本轮跳过：{exc}")
            if do_push:
                last_alert = state.get("last_launch_alert", "")
                today = datetime.now().strftime("%Y-%m-%d")
                if not last_alert.startswith(today):
                    send_push(
                        cfg,
                        "视频号监控：浏览器启动失败",
                        "本轮监控未能启动（Chrome 启动失败，已重试一次）。\n"
                        f"错误：{exc}",
                    )
                    state["last_launch_alert"] = now_str()
                    save_json(STATE_FILE, state)
            return 4
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        ok = goto_private_msg(page, on_login_page=alert_login_failure)

        if is_login_page(page):
            log("登录未恢复，本轮结束。")
            ctx.close()
            return 2

        if not ok:
            log("已登录但未能进入私信页，跳过本轮。")
            ctx.close()
            return 3

        changes_by_tab = {}
        for key, label in TABS:
            if not cfg.get("tabs", {}).get(key, True):
                continue
            snap = collect_snapshot(page, label)
            had_baseline = key in state.get("tabs", {})
            if had_baseline:
                changes = detect_changes(state["tabs"][key], snap["items"])
            else:
                # 首次运行：只建立基线，不把存量消息当成新消息推送
                changes = []
                log(f"tab「{label}」首次初始化：{len(snap['items'])} 条会话记录为基线（不推送）")
            changes_by_tab[(key, label)] = changes
            state.setdefault("tabs", {})[key] = snap["items"]

        total = sum(len(v) for v in changes_by_tab.values())
        if total and do_push:
            lines = []
            for (key, label), changes in changes_by_tab.items():
                for ch in changes:
                    prefix = "新消息" if ch["kind"] == "new" else "未读"
                    lines.append(f"[{label}·{prefix}] {brief(ch['item']['text'], 80)}")
            log("推送内容：" + " ｜ ".join(lines)[:300])
            send_push(cfg, f"视频号私信提醒（{total} 条更新）", "\n".join(lines))
        elif total:
            log(f"发现 {total} 条更新（本次不推送）")
            for (key, label), changes in changes_by_tab.items():
                for ch in changes:
                    log(f"    [{label}] {brief(ch['item']['text'], 80)}")
        else:
            log("无更新。")

        state["last_run"] = now_str()
        save_json(STATE_FILE, state)
        ctx.close()
    return 0


def cmd_loop(cfg: dict) -> int:
    interval = max(60, int(cfg.get("interval_seconds", 300)))
    log(f"进入循环模式，间隔 {interval} 秒（Ctrl+C 退出）")
    while True:
        try:
            run_once(cfg, do_push=True)
        except KeyboardInterrupt:
            log("已停止。")
            return 0
        except Exception as exc:
            log(f"本轮执行出错：{exc}")
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="视频号私信只读监控")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--login", action="store_true", help="扫码登录视频号助手")
    group.add_argument("--check", action="store_true", help="检查登录状态与页面结构")
    group.add_argument("--dump", action="store_true", help="调试：输出页面结构并截图")
    group.add_argument("--once", action="store_true", help="执行一次监控检查（默认模式）")
    group.add_argument("--loop", action="store_true", help="常驻循环模式")
    args = parser.parse_args()

    cfg = load_config()

    lock = acquire_lock()
    if lock is None:
        log("已有另一个实例在运行，本次跳过（避免与定时任务冲突）。")
        return 0
    try:
        if args.login:
            return cmd_login(cfg)
        if args.check:
            return cmd_check(cfg)
        if args.dump:
            return cmd_dump(cfg)
        if args.loop:
            return cmd_loop(cfg)
        return run_once(cfg, do_push=True)
    except Exception as exc:
        # 不把 traceback 抛给 launchd（只进 launchd.err、日常日志无痕迹）：
        # 记入日常日志后干净退出。
        log(f"本次执行异常：{exc}\n{traceback.format_exc()}")
        return 1
    finally:
        try:
            fcntl.flock(lock, fcntl.LOCK_UN)
        except Exception:
            pass
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
