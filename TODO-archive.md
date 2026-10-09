# TODO 归档

（已处理条目的归档；条目正文保留原样可回溯，编号永不复用）

## 🟠 橙色

- [ ] **T1** 生产/开发隔离改造：当前 launchd 直跑开发目录 `~/Developer/channels-watch/watch.py`，违反「运行版本与开发版本隔离」规则（禁止常驻服务直跑开发目录源码）。按 codef 模式建立生产目录部署：从 v0.1.0 Release 产物安装生产副本（如 `~/.local/share/channels-watch/`），迁移运行时数据（`config.json` / `state.json` / `profile/` / `logs/`），launchd 改指向生产副本，并同步更新 README。（记录：2026-10-09 13:31）
  ✅**已完成**（完成：2026-10-09 13:45）——生产副本从 v0.1.0 Release 归档安装到 `~/.local/share/channels-watch/`（watch.py 与开发目录逐字节一致），运行时数据全部迁移，launchd 改指生产副本；bootstrap 后首轮运行正常（「无更新」，launchd.err 为空，进程命令行确认跑的是生产路径）。repo 侧同步更新 plist 模板与双语 README 部署说明、补 CHANGELOG 条目。
