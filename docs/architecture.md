# Symplify Architecture — the calculation Model and its data flow

This page is **Model-first**: it documents the pure-Python calculation core
(`python/model/`), the two requests it answers, where those requests come from,
and who reads what comes back. It is about how data actually moves.

## The Model in one sentence

Two requests, one parser, no Qt:

```python
Calculator.evaluate(expression, scope)      -> Success | Failure   # read
Calculator.assign(Assignment(target, op, expression), scope) -> Success | Failure   # write
```

`Calculator` owns what an input *means* — which syntax is accepted, which names
resolve, what counts as a failure. Nothing above it may re-implement that, and
the Model decides nothing about display.

## 1. Data flow: sources in, sinks out

### 1.1 运行时执行域：主线程、渲染进程、worker 进程

这张图回答“代码在哪跑”，而不是“数据长什么样”。`ProcessBackend` 仍在 Qt 主线程；
计算 worker 和 LaTeX 渲染器都是独立进程。Calculator 的结果/变体与 History 的卡片
共用渲染进程；键盘 keycap 和 Variables 详情仍在主线程同步渲染（短任务，且由
`render_data_url` 的内部锁串行化）。

```mermaid
flowchart LR
    subgraph UI["Qt UI 进程"]
        direction TB

        subgraph MAIN["主线程"]
            QML["QML / RinUI 页面<br/>Calculator · Variables · History · Log · Settings"]
            VM["ViewModels<br/>状态与 Qt 信号"]
            STATE["VariableManager · HistoryModel · LogViewModel<br/>内存状态，UI 持有"]
            PLOT["qmlmathplot<br/>Plot / PlotView（GPU）"]
            PB["ProcessBackend<br/>2 ms 轮询 · 超时 · 取消"]
            IB["InlineBackend<br/>测试 / headless"]
            LOCAL["Calculator<br/>Variables 页同步调用"]
            TEXS["LatexRenderService<br/>LRU 缓存 · token 映射"]
        end
    end

    subgraph RENDER["LaTeX 渲染进程（零 Qt）"]
        TEXW["render_worker_main<br/>ziamath"]
    end

    subgraph WORK["计算 worker 进程（零 Qt）"]
        W["worker_main<br/>Calculator"]
        P["safe AST parser<br/>空 __builtins__"]
        S["SymPy"]
        V["variants()<br/>simplify / doit / N / expand / factor"]
        L["Job Object / rlimits<br/>资源与进程限制"]
    end

    STORE["SettingsStore<br/>YAML，持久化"]

    QML <-->|"属性 / 信号"| VM
    VM <-->|"读写"| STATE
    VM <-->|"设置"| STORE

    VM -->|"请求：id, kind, payload,<br/>scope 快照"| PB
    PB -->|"① 结果 finished"| VM
    PB -->|"② variantsReady<br/>（可选，2 s）"| VM
    VM -.->|"仅测试"| IB
    VM -->|"Variables 页编辑"| LOCAL
    LOCAL <-->|"同进程 scope"| STATE

    PB <-->|"pickled duplex pipe<br/>result / variants"| W
    W --> P
    P --> S
    S --> V
    L -.->|"资源限制"| W

    VM -->|"结果/变体/History LaTeX + style"| TEXS
    TEXS <-->|"pickled pipe"| TEXW
    TEXS -->|"token: SVG + 尺寸"| VM
    VM -->|"曲线 / 主题 / 交互"| PLOT
```

### 1.2 逻辑数据流：Model 语义

> 这一张是**逻辑数据流**，不表示线程位置。实际执行域以 1.1 为准：`C1`–`C4` 在 app 的
> worker 进程里运行；`C6`、输出和 Qt 对象在主线程；`B3`/`B4` 的 Variables 页路径仍是
> 主线程内的同步调用。

```mermaid
flowchart TB
    subgraph IN["① 输入来源"]
        A1["Calculator · Code 模式<br/>calcVM.inputText"]
        A2["Calculator · Assign 模式<br/>assignName / assignOperator / assignValue"]
        A3["Variables 页工具栏<br/>addVariable / updateVariable"]
        A4["Variables 表格内联编辑<br/>setData 第 0 列改名 / 第 1 列改表达式"]
        A5["历史卡片 Send to input<br/>vm.sendToCode / sendToAssign"]
    end

    subgraph VML["② ViewModel 入口（Qt 边界）"]
        B1["CalculatorViewModel.calculate"]
        B2["calculateAssign<br/>构造 Assignment(name, op, 原文)"]
        B3["VariablesViewModel._assign<br/>Assignment(name, '=', 原文)"]
        B4["VariablesModel.setData → _parse"]
        B5["CalculationBackend<br/>InlineBackend (tests) / ProcessBackend (app)<br/>timeout · cancel · stale request ids"]
        C7["Calculator.evaluate / Calculator.assign<br/>Variables 页同步路径（主线程）"]
    end

    subgraph MOD["③ Model（纯 Python · 零 Qt）<br/>app 中在 worker 进程"]
        C1["Calculator.evaluate / Calculator.assign<br/>两个请求，共用一个解析器"]
        C2["unknown_calls 审计<br/>未知调用 → UNKNOWN_NAME<br/>否则 parse_expr（隐式乘法 + convert_xor）"]
        C3["sympy 值"]
        C4["render_latex(value)"]
        C5["Success | Failure"]
    end

    subgraph STATE["③' UI 状态（主线程）"]
        C6["VariableManager<br/>快照字典 name → VariableEntry"]
    end

    subgraph OUT["④ 输出与消费点"]
        D1["resultChanged → 结果区文字 + Copy result"]
        D2["LatexRenderService → render_worker_main（进程）→ token<br/>latexSvgUrl / latexWidth / latexHeight → LatexImage"]
        D3["HistoryModel.add_item → 历史卡片"]
        D4["LogViewModel → LogPage"]
        D5["VariablesModel.save → 变量表"]
        D6["warningOccurred → 遮蔽 sympy 名字的警告 Dialog"]
    end

    A5 -.->|"恢复 VM 字段后由用户触发"| A1
    A5 -.-> A2
    A1 --> B1
    A2 --> B2
    A3 --> B3
    A4 --> B4

    B1 --> B5
    B2 --> B5
    B5 -->|"evaluate / assign + scope"| C1
    B3 --> C7
    B4 -->|"只读求值"| C7
    C1 --> C2
    C2 --> C3
    C3 --> C4
    C4 --> C5
    C2 -.->|"语法 / 域错误"| C5

    C3 -->|"赋值：写回（跨进程）"| C6
    C6 -.->|"list_all() 作为 scope 快照"| C1
    C6 -.->|"同进程 scope"| C7
    C6 -.->|"is_sympy_builtin(name)"| D6
    C7 -->|"同步返回"| R["ViewModel 分发"]

    C5 -->|"返回给调用它的 VM"| R
    R --> D1
    R --> D2
    R -->|"结果，或失败原因"| D3
    R --> D4
    R -->|"仅 Success，且目标已过校验"| D5
```

What the diagram is saying:

- **执行域看 1.1，数据语义看 1.2。** Calculator 的 Code/Assign 请求穿过
  `ProcessBackend`，在 worker 进程里调用 `Calculator`；Variables 页的 B3/B4 仍走
  主线程的 `C7`；Calculator 和 History 的 LaTeX SVG 由独立渲染进程生成。
- **Four UI routes, two model requests.** Code mode, Assign mode, the Variables
  toolbar and the table's inline edit all end in `evaluate` (read) or `assign`
  (write); no route assembles an expression string of its own any more.
- **The Calculator page's two routes cross a backend boundary.** `calculate` /
  `calculateAssign` submit `(kind, payload, scope)` to a `CalculationBackend`
  and return; the `Success | Failure` arrives later as a Qt signal. The default
  backend is synchronous (tests/headless); the app uses a spawned
  `ProcessBackend` with a hard timeout, so a runaway sympy call is terminated
  instead of freezing the event loop. The VM allocates request ids, ignores
  replies for cancelled requests, and cancels the previous request when a new
  one is submitted or the result is cleared. **The result is sent before the
  optional work**: the backend computes `simplify` / `doit` / `N` / `expand` /
  `factor` in the same deadline but delivers those rows later on
  `variantsReady`, so the answer text does not wait for them. The UI requests
  their LaTeX from an isolated renderer process; the result and variant images
  arrive by token. History uses the same process and cache. Timeouts become `Failure(ErrorKind.TIMEOUT)` and are recorded like any
  other failure; the result header shows the backend status. The Variables
  page's own routes (B3/B4) still call the in-process `Calculator` synchronously
  — the next slice of the separation.
- **`scope` is the second input channel.** `VariableManager.list_all()` (valid
  entries only) is handed to `parse_expr` as `local_dict`, so saved variables
  resolve as symbols; names that resolve to nothing stay symbolic.
- **The write path is validated before anything happens.** `assign` rejects a bad
  target or a missing augmented-assignment target *before* evaluating, so a
  rejected write cannot leave a variable or a success log line behind. What it
  *does* leave is an error card in the history — marked as an error, never as a
  result — because the input is what the user needs in order to fix it.
- **`Success.value` is the only output that flows back in.** Assign mode stores
  the sympy object as a `VariableEntry`, and the next request reads it back
  through `list_all()` — the closed loop in the middle of the diagram. The value
  is passed through `sympy.simplify` before it leaves the model (`_simplified`),
  so the store and the next evaluation see the simplified form; lists (`solve`'s
  roots) are exempt, and the plot's `origin` is recorded before the pass.
- **Text and LaTeX are terminal.** `str(value)` feeds the result line and the
  clipboard; the LaTeX source feeds the rendered image and the history entry
  (which re-renders lazily on its own).
- **A plot is the third sink, and it needs provenance.** `plotting.plot_series`
  reads the result's free symbols (`x` → `y = f(x)`, `x` and `y` → the level set
  `F = 0`, anything else → nothing to draw) and, when `Success.origin` says the
  request *was* a transform call, what that call was applied to: `diff` and
  `integrate` draw the function beside the result, `solve` draws the expression it
  solved. `origin` is recorded while the parser runs (a wrapper in its
  `local_dict`), never by re-parsing the text — the model has no parser of its
  own, by design.
- **Failures are history too.** A failed request is recorded with its input
  (name/op/expression for assignments) and the failure text, so the card can
  show the reason and *Send to input* can put the expression back to be fixed.
  The `error` role is what makes a card render as an error card.

## 2. What comes back: `Success` or `Failure`

```mermaid
flowchart LR
    R["Success | Failure<br/>frozen dataclasses"]

    R -->|"Success.value"| V["sympy 对象"]
    V --> V1["str(value) → resultText<br/>结果区文字 + Copy result"]
    V --> V2["_save_variable → VariableManager.save<br/>VariableEntry.obj → list_all() → 下一轮 scope"]
    V --> V3["变量表第 2/3 列<br/>expr_str / classify_type"]
    V --> V4["plot_series(value, origin)<br/>→ qmlmathplot.Plot → PlotView 曲线"]

    R -->|"Success.origin"| O["Origin(call, argument)<br/>求值时由 _TransformRecorder 记录"]
    O --> V4

    R -->|"Success.latex"| L["LaTeX 源串<br/>由 render_latex 生成"]
    L --> L1["LatexRenderService → render_worker_main（进程）→ token<br/>latexSvgUrl / latexWidth / latexHeight → LatexImage 结果区大图"]
    L --> L2["history.add_item(latex=) → 历史卡片 + Copy LaTeX"]

    R -->|"Failure.message / .hint"| E["错误文本"]
    E --> E1["_format_failure → errorMessage → 结果区"]
    E --> E2["LogViewModel.add_error → LogPage"]

    R -.->|"Failure.kind"| K["ErrorKind<br/>决定 VM 是继续写历史/变量表还是停下"]
```

| Shape | Fields | Read by |
|---|---|---|
| `Success` | `expression`, `value`, `latex`, `origin` | `value` → the result line, the variable store, the next evaluation and the plot; `latex` → the result image and the history card; `origin` → what the plot draws beside the result (the function a derivative came from); `expression` → provenance |
| `Failure` | `expression`, `kind`, `message`, `hint` | `message` + `hint` → the result area, the log and the history card; `kind` → which follow-up writes are allowed |

Both are frozen dataclasses, so a caller cannot half-fill a result. The old
`CalculationResult` flag-and-payload struct is gone, and with it the members
nothing ever read (`result_type`, `metadata`, `__str__`, the `displayText`
property, `VariableManager.revision`, `VariablesModel.InvalidRole`).

### Error kinds

| Kind | Meaning |
|---|---|
| `SYNTAX` | the text is not parseable as an expression |
| `UNKNOWN_NAME` | a name used as a call that resolves to no function, or an augmented assignment whose target does not exist |
| `INVALID_NAME` | an assignment target that is not a legal variable name |
| `UNSUPPORTED` | a well-formed request the model does not implement (e.g. `**=`) |
| `INTERNAL` | sympy raised a domain error — never the user's typo |

Every kind is produced somewhere; none is declared speculatively.

## 3. The language rules the Model enforces

**Unknown calls are reported, not rewritten.** `implicit_multiplication` cannot
tell a call from juxtaposition, so it silently turns `bar(2)` into `2*bar`.
`Calculator.unknown_calls` audits the text first and returns `UNKNOWN_NAME` with
a `difflib` suggestion (`sovle(…)` → "did you mean 'solve'?"). Names that *are*
in `scope` are exempt: `f(x)` with `f` a value stays multiplication, which is the
documented meaning of juxtaposition.

**Permissions are otherwise deliberately indulged** (and locked by tests):
unknown *symbols* stay symbolic, `2x` and `x^2` work, `Matrix(...)` is reachable,
and a variable may shadow a sympy name — `sin = 5` makes `sin(x)` mean `5*x`.
That last one is a choice, not an accident; `is_sympy_builtin` warns about it
instead of refusing it.

**Names have one definition.** `validate_name` and `is_sympy_name` are module
functions in `variable.py` used by both the store and the request layer, so the
UI and the Model cannot disagree about what a legal or reserved name is.

## 4. `Assignment`: the only write path

```python
Assignment(target="y", op="+=", expression="2y")
```

- `expression` stays **text**, so the expression language is parsed by exactly
  one parser. The previous implementation rebuilt the write as the string
  `f"{name} {op[0]} ({value})"`, which turned `x += 1` on an undefined `x` into
  the self-referential binding `x = x + 1`.
- Augmented operators (`+= -= *= /= %=`) require the target to exist
  (`UNKNOWN_NAME` otherwise) and combine the stored value with the parsed
  right-hand side — node to node, never text to text.
- The target is validated *first*, which is why an invalid name now produces
  nothing at all instead of "success in the history, absent in the table".

## 5. `VariableManager` — a snapshot store, not a dependency graph

- Entries are **snapshots**: an assignment stores the sympy object it evaluated
  to at that moment. Nothing is re-evaluated when the sources of an expression
  change, and there is no dependency tracking.
- A failed *value* is kept as an **invalid (NaN) entry** (`save_invalid`) so the
  user's raw input — and its row — survives; `list_all()` excludes those entries.
  A failed *name* is not stored at all.
- `classify_type` gives the table's third column (`Integer`, `Matrix`,
  `Invalid`, …); `VariableEntry.expr_str` gives the second.
- `rename` rebuilds the store in order, so a rename keeps the entry's position
  and the table's row order never disagrees with the store's.

## 6. Boundary rule and how to check it

**`python/model/*` never imports Qt.** Every call from the UI crosses a
ViewModel first, and every result comes back as plain data. `main.py` is the
composition root: it builds `MainViewModel`, wires the shared `Calculator` and
`VariableManager` into the ViewModels, and registers them as flat QML context
properties.

The behaviour contract is locked by tests (no framework needed):

```bash
uv run python -m tests.test_model      # model + viewmodels, ~3s
```

They cover the expression language, the error kinds, the assignment rules, the
name tables and the ViewModel invariants (a rejected write leaves nothing
behind). Run them before and after touching the parser or the write path.

## Where settings live (outside the Model)

The Model never sees a settings file. Appearance, rendering and window geometry are
owned by `python/settings.py` (location + YAML + validation) and
`SettingsViewModel`, and RinUI's own theme/backdrop persistence is taken over by
`python/rinui_bootstrap.py` — see "Settings & config" in the developer guide. The
only setting the Model touches is the LaTeX font size, which the viewmodels pass to
`latex_to_svg(size=...)` when they render.
