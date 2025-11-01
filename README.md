# Symplify - Simplify Sympy calculation

一个基于 SymPy 和 PySide6 的图形化符号计算器，支持代数计算、变量管理、历史记录等功能，使用 100% Vibe Coding 实现。

## 功能特性

- **符号计算**：使用 SymPy 进行符号计算
- **变量管理**：支持变量管理
- **可视化界面**：现代化的 GUI 界面，基于 PySide6 和 QFluentWidgets
- **软键盘**：内置软键盘，支持快速输入数学符号和函数
- **历史记录**：保存计算历史，支持复制表达式和结果
- **函数文档**：展示光标位置函数的文档

## 安装依赖

```shell
pip install -r requirements.txt
```

## 运行程序

```shell
python main.py
```

## 打包

### Windows

```shell
python -m nuitka --msvc=latest --lto=yes --windows-console-mode=disable --standalone --enable-plugin=pyside6 --windows-icon-from-ico=./resource/images/Built_with_Qt.ico ./main.py
```

### macOS/Linux

```shell
# Coming soooooon...
```

## 使用说明

### 基本计算

在输入框中输入有效的 SymPy 表达式，如：

- `2*x + 3*x - 5`
- `sin(pi/2) + cos(0)`
- `x**2 + 2*x + 1`

### 变量操作

- **赋值**：`x = 5` 或 `y = sin(pi/4)`
- **增强赋值**：`x += 1` 或 `y *= 2`
- **变量管理**：点击"变量"按钮查看和管理所有变量

## 开发计划

- [ ] 解耦
- [ ] UI Refresh
- [ ] $\LaTeX$渲染支持（基于`mathtext`）
- [ ] 添加绘图功能（基于`matplotlib`）
- [ ] 更丰富的结果展示
- [ ] 支持导出计算结果

## 许可证

### 本项目

本项目采用 GPLV3 许可证，详情请见 LICENSE 文件。

### 使用的开源项目

|Project|License|
|-|-|
|[PySide6](https://doc.qt.io/qtforpython-6/)|[LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only](https://www.qt.io/licensing/open-source-lgpl-obligations)|
|[sympy](https://sympy.org)|[BSD License (BSD)](https://github.com/sympy/sympy/blob/master/LICENSE)|
|[PyQt-Fluent-Widgets](https://qfluentwidgets.com)|[GNU General Public License v3 (GPLv3)](https://github.com/zhiyiYo/PyQt-Fluent-Widgets/blob/PySide6/LICENSE)|
|[Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons)|[MIT License](https://github.com/microsoft/fluentui-system-icons/blob/main/LICENSE)|
|[RainbowBrackets](https://github.com/absop/RainbowBrackets)|[MIT License](https://github.com/absop/RainbowBrackets/blob/master/LICENSE)|
