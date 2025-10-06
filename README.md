# Symplify - Simplify Sympy calculation

一个基于SymPy和PySide6的图形化符号计算器，支持代数计算、变量管理、历史记录等功能。

## 功能特性

- **符号计算**：使用SymPy进行精确的符号计算
- **变量管理**：支持变量赋值、重命名、删除和查看
- **可视化界面**：现代化的GUI界面，基于PySide6和QFluentWidgets
- **软键盘**：内置多套键盘布局，支持快速输入数学符号和函数
- **历史记录**：保存计算历史，支持复制表达式和结果
- **函数文档**：光标悬停可查看函数文档
- **示例功能**：内置常用计算示例
- **计算日志**：记录所有计算过程和结果

## 安装依赖

```shell
pip install sympy pyside6 pyside6-fluent-widgets
```

## 运行程序

```shell
python main.py
```

## 打包

```shell
python -m nuitka --msvc=latest --lto=yes --windows-console-mode=disable --standalone --enable-plugin=pyside6 --windows-icon-from-ico=./resource/images/Built_with_Qt.ico ./main.py
```

## 使用说明

### 基本计算

在输入框中输入有效的sympy表达式，如：

- `2*x + 3*x - 5`
- `sin(pi/2) + cos(0)`
- `x**2 + 2*x + 1`

### 变量操作

- **赋值**：`x = 5` 或 `y = sin(pi/4)`
- **增强赋值**：`x += 1` 或 `y *= 2`
- **变量管理**：点击"变量"按钮查看和管理所有变量

## 开发计划

- [ ] 解耦
- [ ] $\LaTeX$渲染支持（基于`mathtext`）
- [ ] 添加绘图功能（基于`matplotlib`）
- [ ] 支持导出计算结果
- [ ] UI Refresh

## 许可证

### 本项目

本项目采用GPLV3许可证，详情请见LICENSE文件。

### 其他

|Library|License|
|-|-|
|PySide6|[LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only](https://www.qt.io/licensing/open-source-lgpl-obligations)|
|sympy|[BSD License (BSD)](https://github.com/sympy/sympy/blob/master/LICENSE)|
|PyQt-Fluent-Widgets|[GNU General Public License v3 (GPLv3)](https://github.com/zhiyiYo/PyQt-Fluent-Widgets/blob/PySide6/LICENSE)|
