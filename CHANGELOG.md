# Changelog

All notable changes to this project will be documented in this file.

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
