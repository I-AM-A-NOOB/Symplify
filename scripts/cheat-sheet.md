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
- 本地验证：直接启动 `build/main.dist/symplify.exe`，窗口应出现并保持运行（GUI 无控制台；启动失败在事件日志里常是 `0xC0000409`，不是 1）。要 traceback 就临时用 `--windows-console-mode=force` 重新构建
- Qt 6.12 的 Windows/Native style DLL 由 QML 插件加载，Nuitka 的依赖扫描不可靠；`build_windows.py` 在 `prune_qt` 之后显式复制 `Qt6QuickControls2Windows.dll` 与 `Qt6QuickNativeStyle.dll`。缺任何一个都会在 QML 加载时失败，随后在 `QThread` 清理里 abort

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

**发布一条命令**——云端 runner 装不下这个构建：

```bash
uv run python scripts/release.py minor --publish
```

它按顺序做：升版（同步 `pyproject.toml` / `python/version.py` / `uv.lock`）→ 提交并打标签 `vX.Y.Z`（本地）→ 本地构建 → 打包两个下载 → 推送 main 与标签 → `gh release create`（`--generate-notes`）。

两个产物都带平台与架构（跨平台后追加新名字，而不是改名旧文件）：

| 文件 | 内容 |
|---|---|
| `Symplify-vX.Y.Z-windows-x64-portable.zip` | 解压即用：根目录是 `Symplify/`，里面有一个**空的 `data/`** —— 这正是便携模式的开关（`python/settings.py` 的 `resolve_config_dir` 只看 `data` 目录存不存在），配置落在 `data/config.yaml`，不碰目录外任何东西 |
| `Symplify-vX.Y.Z-windows-x64-setup.exe` | Inno Setup 7 编译的安装包（`installer/Symplify.iss`）：默认单用户安装、可选全用户、开始菜单与可选桌面快捷方式、结束页可勾选启动、带卸载项；**故意不带 `data/`**，所以装好的副本把配置放在 `%APPDATA%\Symplify\` |

架构用 `x64` 不是 `amd64`：Windows 自己的叫法，构建里的 DLL（`libcrypto-3-x64.dll`）与 Inno 的 `x64compatible` 都是这个拼法；`platform.machine()` 返回 `AMD64`，映射表在 `release.py` 的 `ARCH_TOKENS`。

安装包需要 [Inno Setup 7](https://jrsoftware.org/isdl.php)（`winget install JRSoftware.InnoSetup.7`）；脚本在 `%LOCALAPPDATA%\Programs`、`Program Files`、`Program Files (x86)` 里找 `Inno Setup */ISCC.exe`，环境变量 `ISCC` 优先。**必须是 7**：脚本用了 `SetupArchitecture=x64` 和 `WizardStyle=modern dynamic`，Inno Setup 6 不认。

两道闸：**工作区必须干净**（否则在任何写入前退出）、**构建产物必须存在**。构建排在推送之前，所以构建失败时远端没有任何需要清理的东西。

要手工分步，等价于：

```bash
uv run python scripts/release.py patch --tag   # 升版 + commit + tag vX.Y.Z
uv run python scripts/build_windows.py         # 本地出包（约 4 分钟，clcache 命中率高）
uv run python -c "import sys; sys.path.insert(0,'scripts'); import release; \
print(release.make_zip('X.Y.Z', release.host_arch())); \
print(release.make_installer('X.Y.Z', release.host_arch()))"
git push origin main; git push origin vX.Y.Z
gh release create vX.Y.Z build/Symplify-vX.Y.Z-windows-x64-*.zip build/Symplify-vX.Y.Z-windows-x64-setup.exe \
  --title "Symplify X.Y.Z" --generate-notes
```

- 单独跑打包（不发布）：`uv run python -c "…make_zip…"` 如上，或直接 `iscc /DMyAppVersion=X.Y.Z installer\Symplify.iss`（`MyAppVersion` 没有默认值，故意让无版本的安装包编不出来）
- 验证产物：`Expand-Archive` 解压便携包后应看到 `Symplify/data/`（空目录只有在归档里显式有条目才能被解压器建出来，这正是它启用便携模式的方式）；安装包 `/?` 有全部参数，`/VERYSILENT /CURRENTUSER /DIR=...` 可无交互装到临时目录再 `unins000.exe /VERYSILENT` 卸载
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
