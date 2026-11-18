# Symplify 数据持久化简介

Symplify 的持久化分成三条独立的线：**设置**、**变量**和**历史记录**。日志、当前结果和绘图不落盘。

## 1. `config.yaml`：应用设置

### 位置

应用启动时先检查程序目录下是否存在 `data/`：

| 模式 | 位置 |
|---|---|
| 便携模式（存在 `<root>/data/`） | `<root>/data/config.yaml` |
| Windows 安装版 | `%APPDATA%\Symplify\config.yaml`（回退到 `%LOCALAPPDATA%`，再回退到用户目录） |
| Linux | `$XDG_CONFIG_HOME/symplify/config.yaml`（回退到 `~/.config/symplify/config.yaml`） |
| macOS | `~/Library/Application Support/Symplify/config.yaml` |

`root` 在冻结版中是 exe 所在目录，在源码运行时是仓库根目录。便携版只是“存在 `data/`”这一个条件；安装版不会创建它。

### 内容与写入规则

`config.yaml` 是易读的 YAML，由 `SettingsStore` 统一读写，主要保存：

- 外观：主题、语言、Mica/Acrylic 背景、强调色；
- 工作区：代码主题、括号配色、字体与字号、键盘布局、空结果水印、Zen 全屏；
- 解析器开关（隐式乘法、`^`、函数应用等）；
- 布局：输入栏宽度、结果/绘图比例、键盘折叠状态、Variables 详情侧边栏的开关和宽度；
- 窗口尺寸与位置（开启“记住窗口”时）。

写入采用**临时文件 + `os.replace` 的原子替换**，避免崩溃或磁盘写满留下半个 YAML。未知键会保留；已知键会校验、夹取到合法范围；文件损坏时回退默认值，并在界面给出警告。配置带有版本号，旧版本会做迁移。

自定义键盘文件位于同一配置目录下的 `keyboards/`，`config.yaml` 只保存当前选择的文件名。

## 2. `variables.json`：变量 Store

### 位置

`variables.json` 与 `config.yaml` 同目录：

- 便携版：`<root>/data/variables.json`
- 安装版：`%APPDATA%\Symplify\variables.json`

### 内容

变量由独立的 Store worker 持有；Store **不导入 SymPy，也不保存 SymPy 对象**，只保存字符串：

- `name`：变量名；
- `srepr`：内部恢复用的 SymPy 规范序列化字符串；
- `display`、`type_label`、`latex`：界面显示；
- `revision`、`valid`：版本与有效性。

`variables.json` 是带 SymPy 版本号的快照，包含当前 revision 和全部条目。每次变量变更后，Store 会原子写入一次；写入失败只报告错误，不会回滚内存中的权威状态。

### 恢复与异常

- 启动时快照若损坏，文件会被改名为 `variables.json.corrupt` 保留现场，应用以空 Store 启动，并在日志中报告原因。
- 快照的 SymPy 版本与当前构建不一致时同样会被搁置，避免恢复出不兼容的对象。
- 完全空的 Store 会通过 `plotting_seeds()` 播种绘图变量 `x`、`y`。
- Compute worker 的 `ScopeCache` 只是缓存；它从 Store 的 `Snapshot`/`Delta` 重建，不能作为变量权威。

## 3. `history.json`：历史记录

历史记录保存在配置目录下的 `history.json`，与 `config.yaml`、`variables.json` 同目录：

- 便携版：`<root>/data/history.json`
- 安装版：`%APPDATA%\Symplify\history.json`

只保存可恢复的字段：输入、结果、错误、模式、变量名/操作符、LaTeX 源、规范化输入、时间。
已渲染的 SVG 和尺寸是缓存，不落盘，启动后由渲染器按需重建。写入同样采用原子替换；超过
500 条时最旧的记录会被淘汰，清空历史也会立即持久化。损坏的历史文件会改名为
`history.json.corrupt` 保留现场，应用从空历史启动。

## 4. 不持久化的内容

以下内容只在当前进程/界面生命周期内存在：

- 日志；
- 当前结果、LaTeX、variants 和绘图；
- 输入框内容（只在页面切换期间由 ViewModel 保留，**重启不保留**）；
- 进行中的计算、撤销/重做栈；
- 历史记录中已缓存的 SVG artwork（会按需重新渲染）。

## 5. 便携版与卸载

- 便携 zip 内置空的 `data/` 目录，因此设置、变量和历史都留在解压目录内；复制整个 `Symplify/` 文件夹即可迁移。
- 安装版把配置放在系统配置目录；卸载程序会询问是否删除配置，不会在未确认时清空数据。

更多内部细节见 [`docs/architecture.md`](architecture.md) 和 [`.Agent/DEVELOPER_GUIDE.md`](../.Agent/DEVELOPER_GUIDE.md) 的 *Store worker* / *Settings & config* 章节。
