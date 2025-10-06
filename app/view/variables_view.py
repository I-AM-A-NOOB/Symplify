from PySide6.QtWidgets import QAbstractItemView, QTableWidgetItem
from qfluentwidgets import (
    CommandBar,
    FluentIcon,
    InfoBar,
    MessageBoxBase,
    SubtitleLabel,
    TableWidget,
    TransparentToolButton,
)

from app.core.calculator import SymbolicCalculator


class VariablesView(MessageBoxBase):
    def __init__(self, symbolic_calculator: SymbolicCalculator, parent=None):
        """变量列表消息框"""
        super().__init__(parent)
        self.calculator = symbolic_calculator  # 保存计算器实例引用
        self.titleLabel = SubtitleLabel("变量列表", self)
        self.viewLayout.addWidget(self.titleLabel)

        # 创建表格显示变量
        self.table = TableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["变量名", "值"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        
        # 添加标志位避免递归
        self.is_updating = False

        # 填充表格数据
        self.update_table(symbolic_calculator.list_variables())

        self.viewLayout.addWidget(self.table)

        # 创建工具栏
        self.toolbar_layout = CommandBar()

        self.add_button = TransparentToolButton(FluentIcon.ADD, self)  # 添加变量的按钮
        self.add_button.clicked.connect(self.add_variable)

        self.delete_button = TransparentToolButton(
            FluentIcon.REMOVE, self
        )  # 删除变量的按钮
        self.delete_button.clicked.connect(self.delete_variable)

        # 添加编辑按钮
        self.edit_button = TransparentToolButton(FluentIcon.LABEL, self)
        self.edit_button.clicked.connect(self.edit_variable)

        # 添加重命名按钮
        self.rename_button = TransparentToolButton(FluentIcon.FONT, self)
        self.rename_button.clicked.connect(self.rename_variable)

        self.toolbar_layout.addWidget(self.add_button)
        self.toolbar_layout.addWidget(self.delete_button)
        self.toolbar_layout.addWidget(self.edit_button)
        self.toolbar_layout.addWidget(self.rename_button)
        self.viewLayout.addWidget(self.toolbar_layout)

        # 监听表格单元格变化
        self.table.cellChanged.connect(self.on_cell_changed)
        # 监听双击事件
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

        self.yesButton.setText("确定")
        self.cancelButton.hide()

        # 用于存储重命名时的原始变量名
        self.original_var_name = None

    def update_table(self, variables):
        """更新表格内容"""
        self.table.setRowCount(len(variables))
        for i, (name, value) in enumerate(variables.items()):
            # 变量名列
            name_item = QTableWidgetItem(name)
            self.table.setItem(i, 0, name_item)

            # 值列
            self.table.setItem(i, 1, QTableWidgetItem(str(value)))

    def add_variable(self):
        """添加新变量"""
        # 生成新的变量名
        new_var_name = self.calculator.generate_var_name()

        # 直接在表格中添加新行
        row_count = self.table.rowCount()
        self.table.setRowCount(row_count + 1)

        # 添加变量名列
        name_item = QTableWidgetItem(new_var_name)

        self.table.setItem(row_count, 0, name_item)

        # 添加值列
        value_item = QTableWidgetItem("0")
        self.table.setItem(row_count, 1, value_item)

        # 选中新添加的行
        self.table.setCurrentCell(row_count, 1)

        # 立即进入编辑状态
        self.table.editItem(value_item)

    def on_cell_changed(self, row, column):
        """处理单元格内容变化"""
        # 检查是否已经在更新中，如果是则直接返回避免递归
        if self.is_updating:
            return
            
        try:
            self.is_updating = True
            
            if column == 1:  # 只处理值列的变化
                var_name = self.table.item(row, 0).text()
                new_value = self.table.item(row, column).text()

                # 使用计算器更新变量
                result = self.calculator.add_variable(var_name, new_value)
                if result.is_error():
                    # 显示错误信息
                    InfoBar.error(
                        title="错误",
                        content=str(result),
                        parent=self,
                        duration=2000,
                    )
                    # 恢复原来的值
                    self.update_table(self.calculator.list_variables())
            elif column == 0 and self.original_var_name:  # 处理变量名的变化（重命名）
                new_var_name = self.table.item(row, 0).text()

                # 使用计算器重命名变量
                result = self.calculator.rename_variable(
                    self.original_var_name, new_var_name
                )
                if result.is_error():
                    InfoBar.error(
                        title="错误",
                        content=str(result),
                        parent=self,
                        duration=2000,
                    )
                    # 恢复原始变量名
                    self.table.item(row, 0).setText(self.original_var_name)
                else:
                    self.update_table(self.calculator.list_variables())
                self.original_var_name = None
        finally:
            # 无论如何都要重置更新标志
            self.is_updating = False

    def rename_variable(self):
        """重命名选中的变量"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            # 记录原始变量名
            self.original_var_name = self.table.item(current_row, 0).text()
            # 允许编辑变量名
            self.table.setCurrentCell(current_row, 0)  # 选中变量名列
            self.table.editItem(self.table.item(current_row, 0))  # 进入编辑模式
        else:
            InfoBar.warning(
                title="警告", content="请先选择一个变量", parent=self, duration=2000
            )

    def on_cell_double_clicked(self, row, column):
        """处理单元格双击事件"""
        # 如果双击的是变量名列，则进入重命名模式
        if column == 0:
            self.original_var_name = self.table.item(row, 0).text()
            self.table.editItem(self.table.item(row, column))
        # 如果双击的是值列，则进入编辑模式
        elif column == 1:
            self.table.editItem(self.table.item(row, column))

    def edit_variable(self):
        """编辑选中的变量"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            # 直接进入编辑状态
            self.table.setCurrentCell(current_row, 1)  # 选中值列
            self.table.editItem(self.table.item(current_row, 1))  # 进入编辑模式
        else:
            InfoBar.warning(
                title="警告", content="请先选择一个变量", parent=self, duration=2000
            )

    def delete_variable(self):
        """删除选中变量"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            var_name = self.table.item(current_row, 0).text()
            # 使用计算器删除变量
            result = self.calculator.delete_variable(var_name)
            if result.is_error():
                # 更新本地变量列表和表格
                InfoBar.error(
                    title="错误",
                    content=f"删除变量 {var_name} 失败",
                    parent=self,
                    duration=2000,
                )

            else:
                self.update_table(self.calculator.list_variables())
        else:
            InfoBar.warning(
                title="警告", content="请先选择一个变量", parent=self, duration=2000
            )
