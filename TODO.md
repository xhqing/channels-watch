# TODO

## 🟠 橙色

- [ ] **T1** 生产/开发隔离改造：当前 launchd 直跑开发目录 `~/Developer/channels-watch/watch.py`，违反「运行版本与开发版本隔离」规则（禁止常驻服务直跑开发目录源码）。按 codef 模式建立生产目录部署：从 v0.1.0 Release 产物安装生产副本（如 `~/.local/share/channels-watch/`），迁移运行时数据（`config.json` / `state.json` / `profile/` / `logs/`），launchd 改指向生产副本，并同步更新 README。（记录：2026-10-09 13:31）

## 🟢 绿色

- [ ] **T2** 接入 CI 基础检查：建 `.github/workflows/ci.yml`（Python 语法检查 / ruff 等基础门禁），接入团队测试防护网（Hopper 体系）。（记录：2026-10-09 13:31）
