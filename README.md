<div align="center">
  <img src="assets/logo.svg" alt="channels-watch" width="640">

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE.md)
  [![Version](https://img.shields.io/badge/Version-0.1.0-blue)](CHANGELOG.md)
  [![Type](https://img.shields.io/badge/Type-Tool-4F46E5)](#)
  [![Visitors](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/xhqing/xhqing/main/traffic/badges/channels-watch.json)](https://github.com/xhqing)

  [简体中文](README_cn.md)
</div>

# channels-watch

A read-only monitor for WeChat Channels (视频号) direct messages: it watches the private-message page of the WeChat Channels Assistant (channels.weixin.qq.com) and **pushes a notification to your phone whenever something new shows up under "Greeting messages" or "Direct messages"**.

## Features

- **Read-only**: it only flips between the two list pages ("Greeting messages" / "Direct messages") and reads them — it never opens a conversation and never sends anything;
- **Low frequency**: one check every 5 minutes by default;
- **Local**: the login session and all message content stay on your machine; pushes carry only a short summary that new messages exist;
- **Multi-channel**: Feishu bot / ntfy / ServerChan, switchable via config;
- **Failure alerts**: if the login session expires, you get a push — no silent message loss.

## How it works

- Playwright drives the local Chrome and opens the private-message page of the WeChat Channels Assistant (the login session is kept in the local `profile/` directory);
- Every run snapshots both lists ("Greeting messages" / "Direct messages") and diffs against the previous snapshot (newly appearing conversations, and conversations that went from read to unread);
- When something changed, a summary is pushed to your phone through the channel you configured;
- Time labels on the conversation entries (like "just now" or "5 minutes ago") are stripped before diffing, so their re-rendering does not cause false alarms.

## Quick Start

### Requirements

- macOS (the launchd scheduling option is macOS-only);
- [Google Chrome](https://www.google.com/chrome/) (the script drives your system Chrome);
- Python 3.11 or newer.

### Step 1: Get the code and install dependencies

```bash
git clone https://github.com/xhqing/channels-watch.git
cd channels-watch
pip3 install playwright
```

### Step 2: Configure a push channel

**Option A: Feishu (recommended; free and reliable)**

> Note: adding a custom bot is a **desktop-only feature** in Feishu (official limitation — the mobile app has no such option). The mobile app is only for receiving messages.

1. Install the Feishu desktop app on your Mac (or use the [feishu.cn](https://www.feishu.cn) web client; also install the mobile app to receive messages);
2. Create a new group in Feishu (just you and/or a secondary account is enough);
3. **On desktop**, open the group → "···" in the top-right → Settings → Group Bots → Add Bot → choose "**Custom Bot**" → set a name and avatar → copy the **Webhook URL** (looks like `https://open.feishu.cn/open-apis/bot/v2/hook/xxxx`);
4. Copy the config template and fill in the webhook URL:

```bash
cp config.example.json config.json
```

```json
{
  "push": {
    "channel": "feishu",
    "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/your-url"
  }
}
```

Test the push (your phone should buzz immediately):

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"msg_type":"text","content":{"text":"channels-watch test message"}}' \
  "your-webhook-url"
```

**Option B: ntfy (open source; Android app available)**

1. Install ntfy on Android (search `ntfy` on Google Play or F-Droid);
2. Subscribe to a **random, hard-to-guess** topic name in the app (e.g. `sph-watch-8f3k2m` — the topic name is the password);
3. Edit `config.json`:

```json
{
  "push": {
    "channel": "ntfy",
    "ntfy": { "server": "https://ntfy.sh", "topic": "sph-watch-8f3k2m" }
  }
}
```

Test (your phone should buzz immediately):

```bash
curl -d "channels-watch test message" ntfy.sh/sph-watch-8f3k2m
```

> If ntfy.sh is unreliable from your network, self-host a server and point `server` at it — or just use the Feishu option.

**Option C: ServerChan**

Apply for a SendKey at [sct.ftqq.com](https://sct.ftqq.com), then:

```json
{
  "push": {
    "channel": "serverchan",
    "serverchan_key": "your-SendKey"
  }
}
```

### Step 3: First login (scan the QR code)

```bash
python3 watch.py --login
```

In the Chrome window that pops up, scan the QR code with **the WeChat account bound to your Channels profile**. The window closes automatically once login succeeds, and the session is saved in the `profile/` directory (you normally will not need to log in again).

> After the server revokes the session, the login page first attempts a "remembered-account quick login" (it shows the last account name and "logging in...") and usually completes within 10–15 seconds without any QR scan — `--login` waits for it automatically.

### Step 4: Verify

```bash
python3 watch.py --check     # check login status and whether the conversation list can be read
python3 watch.py --once      # run one monitoring pass manually (pushes if there are updates)
```

Send a DM or greeting to your Channels profile from another WeChat account, then run `--once` — your phone should receive a push.

### Step 5: Schedule it (choose one)

**Option A: launchd job (recommended — starts at login, runs silently in the background)**

```bash
# First edit com.xhq.channels-watch.plist, replacing /Users/YOUR_USERNAME/Developer/channels-watch
# with the path where you actually cloned the repo (3 occurrences: ProgramArguments, WorkingDirectory, log paths)
cp com.xhq.channels-watch.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.xhq.channels-watch.plist
```

- Runs once every 5 minutes; logs go to `logs/`;
- To stop: `launchctl unload ~/Library/LaunchAgents/com.xhq.channels-watch.plist`

**Option B: foreground loop (for debugging)**

```bash
python3 watch.py --loop
```

## FAQ

**Q: How often does the login session expire, and what do I do?**
The server revokes the web session from time to time; we have observed it being revoked in under a day (no fixed period).

Most of the time **no QR scan is needed**: the login page first attempts a "remembered-account quick login" (showing the last account name and "logging in..."), which usually completes within 10–15 seconds. The script waits up to 40 seconds for it, so monitoring recovers automatically and you are not alerted.

Only when the script reports a session failure — i.e. even the quick login did not finish within the grace period and the page is asking for a QR scan — do you need to run `python3 watch.py --login` again.

**Q: Push notifications are not arriving. How do I troubleshoot?**
1. Run the test push command from Step 2 first, to rule out the push channel itself;
2. Check the latest log under `logs/` to see whether it says "no updates" or shows an error;
3. If it cannot read the conversations (most likely a page redesign), run `python3 watch.py --dump` — it saves a screenshot and page-structure info; submit those to [Issues](https://github.com/xhqing/channels-watch/issues).

**Q: Will it produce false alarms?**
It de-duplicates as much as it can (read state + content fingerprints), but time-label quirks on the page can still cause a few duplicate notifications.

**Q: Will it affect my Channels account?**
The script is deliberately "read-only + low-frequency", but it still falls in the gray zone of Section 4.3 of the WeChat Channels Operation Rules (third-party tooling). No zero-risk guarantee can be made — run it at low frequency for a week or two and watch your account status first.

## Repository layout

```
channels-watch/
├── watch.py                    # main script
├── config.example.json         # config template (copy to config.json and edit)
├── config.json                 # your config (contains webhooks etc.; never committed)
├── com.xhq.channels-watch.plist# launchd job template (macOS)
├── assets/logo.svg             # project logo
├── profile/                    # browser login session (auto-generated; do not touch)
├── logs/                       # run logs (auto-generated)
├── state.json                  # de-dup state (auto-generated)
├── CHANGELOG.md                # change log
└── VERSION                     # version number
```

## Environment

- macOS (verified on: Python 3.11 + Playwright + Google Chrome);
- Your Mac needs to stay on and online (or at least be on during the hours you want monitored).

## License & Attribution

Copyright (c) 2026 All Contributors. Released under the [MIT License](LICENSE.md).

Attribution: if you use or reference this project, please keep the copyright notice and credit the source: [channels-watch](https://github.com/xhqing/channels-watch).
