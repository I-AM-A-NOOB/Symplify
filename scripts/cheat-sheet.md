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
- tag `vX.Y.Z` 只是版本标记，**不再触发云端出包**（原因见下）

## CI / Release

**发布走本地构建**——云端 runner 装不下这个构建：

```bash
uv run python scripts/release.py patch --tag   # 升版 + commit + tag vX.Y.Z
git push origin main --tags                    # 推版本与标签
uv run python scripts/build_windows.py         # 本地出包（约 4 分钟，clcache 命中率高）
powershell -NoProfile -Command "Compress-Archive -Path 'build\main.dist' -DestinationPath 'symplify-vX.Y.Z.zip' -Force"
gh release create vX.Y.Z symplify-vX.Y.Z.zip --title "Symplify X.Y.Z" --notes "…"
```

- **为什么不在云端出包**：修掉 `fontTools.pens.momentsPen` 之后仍失败三次——`sympy.polys.polyquinticconst` 生成的 C 有 26k 行，MSVC 第二遍报 `fatal error C1002`（堆空间不足）。`--low-memory` 把失败面从 5 处收到 1 处，再加 `--jobs=1` 仍未通过；同一提交本机约 4 分钟编过。这是 runner 内存的硬墙，不是配置问题
- **workflow 只保留手动触发**（Actions → *Windows build (Nuitka)* → *Run workflow*，或 `gh workflow run build-windows.yml`）：用于在别处复现构建，产物在该次运行的 Artifacts 里；它**不再**创建 Release
- 本地构建 = 同一脚本：`uv run python scripts/build_windows.py`；跑 `build/main.dist/symplify.exe` 看能否存活即验证

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
uv run python -c "import tempfile; from pathlib import Path; from python.settings import SettingsStore; \
from python.viewmodel.main_viewmodel import MainViewModel; \
vm=MainViewModel(SettingsStore(Path(tempfile.mkdtemp())/'config.yaml')); \
vm.calculator.calculate('diff(x**2, x)'); print(vm.calculator._result_text)"
```
