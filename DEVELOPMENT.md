# channels-watch 项目指南

## 负责工程师：Atlas

本项目由 **Atlas**（FullStackEngineerAgent，用户的全栈开发工程师）负责维护。Atlas 负责本项目的全部开发工作——脚本功能迭代、发布流程、部署维护。在本项目内的开发 / 维护需求，由 Atlas 统一处理（Atlas 的角色定义与工作原则见 FullStackEngineerAgent 项目根 `CLAUDE.md`）。

channels-watch 是一个视频号私信监控工具：用 Playwright 驱动本机 Chrome 打开微信视频号助手（channels.weixin.qq.com）的私信页，只读监控「打招呼消息 / 私信」两个列表，发现新内容时通过飞书 / ntfy / Server酱推送到手机。Python + Playwright，macOS 上由 launchd 定时运行。

## 项目核心原则

- **只读红线**：绝不点进会话、绝不发送任何消息、绝不改变视频号账号的任何状态——一切改动以不破坏这一原则为前提（这是用户对账号安全的底线，也写在 README 的合规声明里）；
- **低频**：默认 5 分钟一轮，不要不经用户同意提高频率；
- **敏感信息不入库**：`config.json`（Webhook / SendKey）、`state.json`（含私信内容）、`logs/`（运行日志）、`profile/`（登录态）一律 gitignore，改 `.gitignore` 时注意保持这些条目。

## 登录态机制（2026-10-09 修复，勿回退）

- 服务端会不定期吊销网页登录态（两次实测均在登录后不足一天内）；
- 吊销后登录页会先尝试「记住账号快速登录」（显示上次登录的账号 + 「登录中...」，实测 10~15 秒自动完成、无需扫码）——`goto_private_msg` 内置 40 秒宽限等待（`QUICK_LOGIN_GRACE_SECONDS`），等不到才判真·未登录并告警；`cmd_login` 同样先等快速登录完成再决定是否提示扫码；
- 2026-10-09 之前曾因固定 6 秒就检查、把快速登录过程误报成「登录失效」（连续多轮），改动相关逻辑时注意保留宽限机制。

## 工作纪律

- 通用工作规则见全局 `~/.claude/CLAUDE.md`：读取优先、增改查优先慎用删除、汇报前验证、临时产物放 `tmp/`、改动记 `CHANGELOG.md`、待办记 `TODO.md`。
- 运行版本与开发版本隔离：生产运行不得直跑开发目录源码——已从 v0.1.0 Release 安装生产副本到 `~/.local/share/channels-watch/`，launchd 指向生产副本（2026-10-09 完成，见 CHANGELOG）；开发在 `~/Developer/channels-watch` 进行，升级时只替换生产目录里的 `watch.py`。开发目录已无运行时数据（配置 / 登录态 / 去重状态都在生产目录），开发跑 `--check` 前需自备登录态（从生产目录复制 `profile/`，或在开发目录跑一次 `--login`）。
- 改动 `watch.py` 后必须实际验证：至少跑一次 `python3 watch.py --check` 确认能进私信页、能抓到会话列表。
- `QUICK_LOGIN_GRACE_SECONDS`、比对去噪（`TIME_NOISE_RE`）等稳定性相关逻辑改动前，先读本文件与 CHANGELOG 对应条目，避免回归。


（本文件 2026-10-12 由原 `CLAUDE.md` 的项目指南迁入；按新规，非 Agent 项目不再保留 CLAUDE.md / AGENTS.md 等智能体专属文件。）
