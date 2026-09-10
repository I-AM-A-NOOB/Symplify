# Symplify Architecture — the calculation Model and its data flow

This page is **Model-first**: it documents the pure-Python calculation core
(`python/model/`), where its inputs come from, and who reads each field of what
it hands back. The static layer/type map lives in [`architecture.svg`](architecture.svg);
this page is about how data actually moves.

## The Model in one sentence

`Calculator.evaluate(expression, variables) -> CalculationResult` — **one entry
point, zero Qt, never raises**. Everything else in `python/model/` exists either
to feed it (`VariableManager`) or to describe what came back
(`CalculationResult`). Any change to the calculation behaviour belongs there,
and only there.

## 1. Data flow: sources in, sinks out

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
        B1["CalculatorViewModel.calculate<br/>calculator_viewmodel.py:233"]
        B2["calculateAssign<br/>:250"]
        B3["VariablesViewModel._parse_value<br/>variables_viewmodel.py:329"]
        B4["VariablesModel._parse<br/>:102"]
    end

    subgraph MOD["③ Model（纯 Python · 零 Qt）"]
        C1["Calculator.evaluate(expression, variables)<br/>calculator.py:73"]
        C2["parse_expr<br/>standard + implicit_multiplication + convert_xor<br/>local_dict = variables"]
        C3["sympy 表达式对象"]
        C4["sympy.latex(value)"]
        C5["CalculationResult"]
        C6["VariableManager<br/>快照字典 name → VariableEntry"]
    end

    subgraph OUT["④ 输出与消费点"]
        D1["resultChanged → 结果区文字 + Copy result"]
        D2["latexSvgUrl / latexWidth / latexHeight → LatexImage"]
        D3["HistoryModel.add_item → 历史卡片"]
        D4["LogViewModel → LogPage"]
        D5["VariablesModel.save → 变量表"]
        D6["warningOccurred → 内置名警告 Dialog"]
    end

    A5 -.->|"恢复 VM 字段后由用户触发"| A1
    A5 -.-> A2
    A1 --> B1
    A2 --> B2
    A3 --> B3
    A4 --> B4

    B1 --> C1
    B2 -->|"增强赋值先展开成 name op (value)"| C1
    B3 -->|"各自 new Calculator()"| C1
    B4 -->|"各自 new Calculator()"| C1

    C1 --> C2
    C2 --> C3
    C3 --> C4
    C4 --> C5
    C1 -.->|"解析/求值抛异常"| C5

    C3 -->|"赋值：result.value"| C6
    C6 -.->|"list_all() 作为 variables 入参"| C1
    C6 -.->|"is_sympy_builtin(name)"| D6

    C5 -->|"返回给调用它的 VM"| R["ViewModel 分发"]
    R --> D1
    R --> D2
    R --> D3
    R --> D4
    R -->|"assign：_save_variable"| D5
```

What the diagram is saying:

- **Four entry points converge on one function.** Code mode
  (`CalculatorViewModel.calculate`), Assign mode (`calculateAssign`, which first
  expands `+= -= *= /= %=` into the expression `name <op> (value)`), the
  Variables-page toolbar, and the Variables table's inline edit all end at
  `Calculator.evaluate`. The first two use the shared `Calculator` instance from
  `MainViewModel`; the two Variables paths build a throwaway `Calculator()` each.
- **`variables` is the second input channel.** `VariableManager.list_all()`
  (valid entries only) becomes `parse_expr`'s `local_dict`, so saved variables
  resolve as symbols; expressions that reference unknown names stay symbolic.
- **`result.value` is the only output that flows back in.** Assign mode stores
  the sympy object as a `VariableEntry`, and the next evaluation reads it back
  through `list_all()` — the closed loop in the middle of the diagram. History,
  log and the result area are terminal consumers.
- **Text and LaTeX are terminal.** `str(value)` feeds the result line and the
  clipboard; the LaTeX source feeds the rendered result image and the history
  entry (which re-renders lazily on its own).

## 2. `CalculationResult`: every field, and who reads it

```mermaid
flowchart LR
    CR["CalculationResult<br/>calculator.py:34"]

    CR -->|"success：唯一被分支判断的字段<br/>读点 4 处"| S["calculate:239 · calculateAssign:271<br/>VariablesModel._parse:105<br/>VariablesViewModel._parse_value:334"]

    CR -->|value| V["sympy 对象"]
    V --> V1["str(value) → _result_text → resultText<br/>结果区右上文字 + Copy result"]
    V --> V2["_save_variable → VariableManager.save<br/>VariableEntry.obj → list_all() → 下一轮 local_dict"]
    V --> V3["_parse / _parse_value 的返回值<br/>→ VariablesModel.save"]

    CR -->|latex| L["LaTeX 源串"]
    L --> L1["_build_latex_url → latexSvgUrl / latexWidth / latexHeight<br/>→ LatexImage 结果区大图"]
    L --> L2["history.add_item(latex=) → LatexRole / LatexUrlRole<br/>→ 历史卡片 LaTeX + Copy LaTeX"]

    CR -->|error| E["错误串"]
    E --> E1["_error_message → errorMessage → 结果区文字"]
    E --> E2["LogViewModel.add_error → LogPage"]

    CR -.->|"从未被读取"| X["result_type<br/>metadata<br/>__str__"]
```

| Field | Written at | Read at | Reaches the UI as |
|---|---|---|---|
| `success` | `calculator.py:91` / `:98` | 4 call sites (both VMs) | the branch that decides result vs. error |
| `value` | `calculator.py:93` | `calculator_viewmodel.py:217`, `:244`, `:281`; `variables_viewmodel.py:107`, `:336` | `resultText`, the variables table, the next evaluation |
| `latex` | `calculator.py:94` | `calculator_viewmodel.py:218`, `:221`, `:242`, `:277` | the rendered result image, `Copy LaTeX`, the history card |
| `error` | `calculator.py:98` | `calculator_viewmodel.py:226`, `:247`, `:285`; `variables_viewmodel.py:106`, `:335` | the error text in the result area, the log |
| `result_type` | `calculator.py:92` / `:98` | **nothing** | — (`ResultType.ASSIGNMENT` is never even produced) |
| `metadata` | never | **nothing** | — |

Two more members of the same family, outside this dataclass:

- `CalculationResult.__str__` (`calculator.py:54`) — no callers; both VMs use
  `str(result.value)`.
- `CalculatorViewModel.displayText` (`calculator_viewmodel.py:197`) — declared to
  "cut QML→Python round-trips" by merging error/LaTeX, but no QML binds it; the
  result area reads `isError` + `errorMessage` + `resultText` instead.

## 3. `VariableManager` — a snapshot store, not a dependency graph

- Entries are **snapshots**: an assignment stores the sympy object it evaluated
  to at that moment. Nothing is re-evaluated when the sources of an expression
  change, and there is no dependency tracking.
- A failed assignment (`=` in Assign mode, or an unparsable inline edit) is kept
  as an **invalid (NaN) entry** (`save_invalid`) so the user's raw input — and
  its row — survives; `list_all()` excludes those entries from evaluation.
- `validate_name` enforces identifier rules (leading letter/underscore, then
  alnum/underscore, not a Python keyword). It runs **late** — inside
  `save`/`save_invalid`, not in the UI or the ViewModel — so an illegal name like
  `1x` still evaluates, still lands in history, and only fails to be stored
  (logged as a warning by `_save_variable`).
- `is_sympy_builtin` (known constants plus a generic `hasattr(sympy, name)`
  probe) drives the "… is a SymPy built-in. You asked for it." warning dialog; it
  is checked by both the calculator and the variables ViewModels.
- `classify_type` maps a sympy object to the coarse type label shown in the
  table's third column; `VariableEntry.expr_str` (the canonical `str(obj)`, or
  the raw input when invalid) is the second column.
- `revision` / `_touch` exist for cache invalidation but **have no readers**, and
  `VariablesModel.InvalidRole` (exposed to QML as `invalid`) is unused as well —
  invalid rows are recognisable in the UI only through their `Invalid` type label.

## 4. Boundary rule

**`python/model/*` never imports Qt.** Every call from the UI crosses a
ViewModel first, and every result comes back as plain data
(`CalculationResult` / `VariableEntry`). `main.py` is the composition root: it
builds `MainViewModel`, wires the shared `Calculator` and `VariableManager` into
the ViewModels, and registers them as flat QML context properties.

The Model also decides **nothing about display**: rendering (`latex_render.py`),
theme colouring, clipboard and focus navigation all live in the ViewModel or
above. That is why the Model can be exercised headless:

```bash
uv run python -c "from python.viewmodel.main_viewmodel import MainViewModel; \
vm=MainViewModel(); vm.calculator.calculate('diff(x**2, x)'); print(vm.calculator._result_text)"
```
