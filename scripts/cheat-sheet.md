# Symplify — Command Cheat Sheet

日常命令速查（在仓库根目录执行）。

## 开发环境

```bash
uv sync                          # 安装依赖（含 dev 组：Nuitka）
uv run python main.py            # 运行应用
```

> 依赖变更后：`uv add <pkg>` / `uv add --dev <pkg>`，别手改锁文件。

## 构建 Windows 发行版（Nuitka）

```bash
uv run python scripts/build_windows.py
```

- 输出：`build/main.dist/symplify.exe`（单目录、MSVC、无控制台窗口）
- 要求本机装有 Visual Studio Build Tools（`cl` 可解析）；CI 在 `windows-latest` 上等价执行
- `build/` 已 gitignore，不会误提交

### 已知打包坑（改依赖时留意）

- `ziamath`/`ziafont` 的字体、`latex2mathml` 的符号表、RinUI 的 QML 树都要通过
  `--include-package(-data)` 显式带上（脚本里已配好）；**加了会读数据文件的新依赖时，先在脚本里补 include 规则**
- 新依赖若用 `importlib.resources` 加载资源，其子包需 `--include-module=...`（Nuitka 发现不了字符串引用）
- 本地验证：直接跑 `build/main.dist/symplify.exe` 看是否存活（GUI 无控制台，崩了 exit code=1；临时加 `--windows-console-mode=force` 可看 traceback）

## 版本管理（SemVer）

```bash
uv run python scripts/release.py patch          # 0.1.0 -> 0.1.1
uv run python scripts/release.py minor          # 0.1.0 -> 0.2.0
uv run python scripts/release.py major          # 0.1.0 -> 1.0.0
uv run python scripts/release.py 0.3.5          # 显式指定
uv run python scripts/release.py minor --tag    # 升版 + 自动 commit + tag v0.2.0
```

- 权威版本在 `pyproject.toml`；`python/version.py` 是运行时副本（About 页显示），脚本自动同步两者
- tag `vX.Y.Z` 会触发 GitHub Action：打包 + 自动创建 Release（见下）

## CI / Release

```bash
uv run python scripts/release.py minor --tag   # 升版并打 tag v0.2.0
git push origin main --tags                    # 推送后 CI 自动构建
```

- **tag 触发**：推 `v*` → GitHub Actions（windows-latest）构建 `build/main.dist` → 自动打成 `symplify-vX.Y.Z.zip` → **自动创建 Release**（附 zip、release notes 自动生成）。完成后在仓库 Releases 页可见，可再编辑标题/正文
- **手动触发**（不发 Release）：仓库 Actions → *Windows build (Nuitka)* → *Run workflow* → 完成后在该次运行的 **Artifacts** 下载
- Release 由默认 `GITHUB_TOKEN` 创建（workflow 已声明 `contents: write`），无需额外配置
- 本地构建 = 同一脚本：`uv run python scripts/build_windows.py`

## Git

```bash
git status / git diff              # 查看
git add -A && git commit -m "..."  # 提交
git push origin main               # 推送（远端分支 v1/v2/v3 见下）
```

分支路线：`main`（RinUI+PySide6/QML，当前）；`v3-fluentwinui3-qml`（第三版 FluentWinUI3）；`v1-/v2-qfluentwidget`（早期 QWidget 版，历史参考）。

## 给 Agent 的文档

- `.Agent/DEVELOPER_GUIDE.md` — 源码结构、架构不变量、RinUI/Qt 坑、构建与版本说明（**Agent 重大改动后须同步更新**）
- `AGENTS.md`（根目录）— 指向上面的指南与维护条款

## 快速自检

```bash
uv run python -c "from python.viewmodel.main_viewmodel import MainViewModel; \
vm=MainViewModel(); vm.calculator.calculate('diff(x**2, x)'); print(vm.calculator._result_text)"
```
