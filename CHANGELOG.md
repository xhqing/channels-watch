# Changelog

All notable changes to this project will be documented in this file.

## [未发布]

### Changed

- **告警时机：只在自动恢复确实失败后才推送**（2026-10-10 用户要求「恢复失败才推」）。为什么改：0.1.4 的告警回调在点击「微信快捷登录」后立即触发——成功恢复（含确认窗口内人工点「允许」）也会收到提醒。改了什么：回调挪到恢复流程走完、仍判定未登录时统一调用——成功恢复保持静默；点到按钮但 300 秒窗口耗尽、或未点到按钮时才推送（按日去重口径不变）。

## [0.1.4] - 2026-10-10

### Fixed

- **登录态吊销后无法自愈（2026-10-10 事故）**：微信 4.x 桌面端的快捷登录需真人在「视频号创作平台 申请使用」弹窗点「允许」，旧流程只等 `is_login_page` 翻转、从不点击 → 连续 7 小时无法恢复。修复：宽限等待后点击 iframe 内的「微信快捷登录」（遍历 `page.frames`），并在 300 秒窗口内每 90 秒重发请求（微信弹窗超时可再请求），人工确认后自动完成登录并继续本轮监控。
- **登录告警文案误导**：原文案写死开发目录 `cd ~/Developer/channels-watch`，而 launchd 跑的是生产副本 `~/.local/share/channels-watch`（profile 独立）→ 改为按运行副本（`BASE_DIR`）动态生成，并补充「若屏幕出现微信『申请使用』确认框，点『允许』即可恢复」。
- **Chrome 启动失败无痕**：启动失败改为记日常日志 + 重试一次；仍失败则干净退出（不把 traceback 抛给 launchd）并发出告警（按日去重）；未捕获异常一并记入日常日志。

## [0.1.3] - 2026-10-09

### 变更

- **同步 Atlas 子项目清单（zcode-cli、cmux-launcher 短期搁置标注）**。为什么改：用户 2026-10-09 决定 zcode-cli 与 cmux-launcher 短期不再维护，Atlas 权威源已作标注，按超集规则本仓库随附版同步。改了什么：随附的 FullStackEngineerAgent CLAUDE.md 全文更新——「目前在手项目」与「当前子项目清单」两处标注两者「自 2026-10-09 起短期搁置」。

## [0.1.2] - 2026-10-09

### 变更

- **同步 Atlas 子项目清单（加入 mp4-player）**。为什么改：Atlas 权威源把 mp4-player 登记为新子项目，按超集规则各子项目的随附版需同步（本文件末尾的 FullStackEngineerAgent CLAUDE.md 全文）。改了什么：随附版全文更新——「目前在手项目」与「当前子项目清单」两处加入 mp4-player。

## [0.1.1] - 2026-10-09

### Changed

- **生产/开发隔离：服务改为运行已安装副本，不再直跑开发目录**（2026-10-09）。为什么改：launchd 原先直接运行 `~/Developer/channels-watch/watch.py`，违反「运行版本与开发版本隔离」规则（禁止常驻服务直跑开发目录源码）。改了什么：①生产副本从 v0.1.0 Release 归档安装到 `~/.local/share/channels-watch/`（`watch.py` 与开发目录逐字节一致）；②launchd 任务改指生产副本（ProgramArguments / WorkingDirectory / 日志路径）；③运行时数据（`config.json` / `state.json` / `profile/` / `logs/`）迁移到生产目录——登录态与去重状态延续，无需重新登录、不会重复推送；④launchd 模板（`com.xhq.channels-watch.plist`）与双语 README 补充生产部署说明（从 Release 安装、升级只替换 `watch.py`）；⑤`TODO.md` T1 归档。

## [0.1.0] - 2026-10-09

### Added

- **项目立项并开源（初版 0.1.0）**。为什么改：`channels-watch` 此前是用户本机的一个自用工具（2026-10-07 建立），用于监控视频号私信、发现新消息推送到手机；2026-10-08 / 10-09 两轮「登录失效」告警经排查确认为脚本误报并修复后，2026-10-09 用户决定正式立项——开源为公开仓库，并交由 Atlas（FullStackEngineerAgent）负责维护。改了什么：①补全项目标配——中英双语 README（`README.md` 英文 / `README_cn.md` 中文，含 logo 与徽章）、MIT `LICENSE.md`、`VERSION`、本 CHANGELOG、`.gitignore`、`TODO.md` / `MEMO.md`；②launchd 模板 `com.xhq.channels-watch.plist` 的绝对路径改为 `/Users/YOUR_USERNAME/...` 占位符（使用者 clone 后按实际路径替换）；③新建项目 `CLAUDE.md`（负责工程师 Atlas + 项目原则 + Atlas 全文随附）；④开源到 GitHub（xhqing/channels-watch），登记进全局注册表映射表与 Atlas 子项目清单。
- **视频号私信只读监控主脚本（`watch.py`）**：Playwright 驱动本机 Chrome → 打开视频号助手私信页（登录态存本机 `profile/`）→ 对比「打招呼消息 / 私信」两个列表快照（比对时剔除时间文案噪声）→ 有变化推送到飞书 / ntfy / Server酱；launchd 每 5 分钟一轮。支持 `--login`（扫码登录）/ `--check`（检查状态）/ `--once`（单轮）/ `--loop`（前台循环）/ `--dump`（调试截图）。

### Fixed

- **修复「登录失效」误报（快速登录宽限等待）**。为什么改：2026-10-08 18:35 起与 10-09 11:57 起两轮「登录态可能已失效」告警均为误报——服务端吊销网页登录态后，登录页会先尝试「记住账号快速登录」（显示上次登录的账号 + 「登录中...」，实测 10~15 秒内自动完成、无需扫码），而脚本固定在页面加载 6 秒后就检查登录状态，快速登录还没走完就被判「失效」并关闭浏览器（快速登录永远无法完成），导致连续多轮误报。改了什么：①`goto_private_msg` 落在登录页时先宽限等待（`QUICK_LOGIN_GRACE_SECONDS = 40`，每 2 秒轮询），快速登录完成则继续监控、等不到才判真·未登录；②`cmd_login` 同样先等快速登录完成再决定是否提示扫码（不再误导用户扫码），扫码等待循环加一次「双检」防止页面导航瞬间误判「登录成功」。

### Project

- **归属与治理**：开源至 GitHub（[xhqing/channels-watch](https://github.com/xhqing/channels-watch)），由 **Atlas**（FullStackEngineerAgent）负责维护；生产 / 开发隔离改造（当前 launchd 直跑开发目录，需改为从 Release 产物部署）见 `TODO.md` T1。
