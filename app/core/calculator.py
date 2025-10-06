import ast
import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication,
    parse_expr,
    standard_transformations,
)


class Result:
    def __init__(self, content: str, is_success: bool = False):
        self.content = content
        self.is_success_flag = is_success

    def __str__(self):
        return str(self.content)

    def is_success(self):
        return self.is_success_flag

    def is_error(self):
        return not self.is_success_flag


class ExpressionHandler:
    """表达式处理核心类，统一处理赋值和计算逻辑"""

    def __init__(self):
        self.variables = {}  # 存储用户定义的变量
        self.transformations = standard_transformations + (
            implicit_multiplication,
            convert_xor,
        )

    def is_valid_variable_name(self, name: str) -> bool:
        """检查变量名是否合法"""
        try:
            tree = ast.parse(f"{name} = 0")
            if (
                len(tree.body) == 1
                and isinstance(tree.body[0], ast.Assign)
                and len(tree.body[0].targets) == 1
                and isinstance(tree.body[0].targets[0], ast.Name)
                and tree.body[0].targets[0].id == name
            ):
                return True
            return False
        except SyntaxError:
            return False

    def is_assignment(self, expression: str) -> bool:
        """使用AST判断输入是否为赋值语句"""
        try:
            tree = ast.parse(expression)
            # 检查是否只有一个语句且为赋值语句或增强赋值语句
            if len(tree.body) == 1 and isinstance(
                tree.body[0], (ast.Assign, ast.AugAssign)
            ):
                return True
            return False
        except SyntaxError:
            # 如果不是有效的Python语法，可能只是一个表达式
            return False

    def parse_assignment(self, expression: str) -> tuple[list[str], str]:
        """解析赋值语句，提取变量名和表达式"""

        tree = ast.parse(expression)
        node = tree.body[0]

        # 处理普通赋值
        if isinstance(node, ast.Assign):
            # 获取左侧所有目标变量
            targets = []
            for target in node.targets:
                if isinstance(target, ast.Name):
                    targets.append(target.id)
                else:
                    raise TypeError(f"不支持的赋值目标类型: {type(target).__name__}")
            expr_str = ast.get_source_segment(expression, node.value)
            return targets, expr_str

        # 处理增强赋值
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                target = node.target.id

                # 获取操作符对应的符号运算
                op_map = {
                    ast.Add: "+",
                    ast.Sub: "-",
                    ast.Mult: "*",
                    ast.Div: "/",
                    ast.FloorDiv: "//",
                    ast.Mod: "%",
                    ast.Pow: "**",
                }

                op_char = op_map.get(type(node.op), "")
                if not op_char:
                    raise ValueError(f"不支持的操作符: {type(node.op).__name__}")

                right_expr = ast.get_source_segment(expression, node.value)

                # 构建完整表达式
                expr_str = f"{target} {op_char} ({right_expr})"
                return [target], expr_str
            else:
                raise TypeError("增强赋值的目标必须是简单变量")

        else:
            raise TypeError("不支持的赋值语句类型")

    def evaluate_expression(self, expression: str):
        """计算表达式并返回结果"""

        parsed_expr = parse_expr(
            expression,
            local_dict=self.variables,
            transformations=self.transformations,
        )
        if isinstance(parsed_expr, (sp.Sum, sp.Product)):
            parsed_expr = parsed_expr.doit()
        return parsed_expr


class SymbolicCalculator:
    """符号计算引擎，使用AST检测赋值语句"""

    def __init__(self):
        self.expression_handler = ExpressionHandler()

    def process_expression(self, expression: str) -> Result:
        """计算表达式并返回结果或错误信息"""
        # 检查是否为赋值语句
        if self.expression_handler.is_assignment(expression):
            try:
                # 解析赋值语句
                targets, expr_str = self.expression_handler.parse_assignment(expression)
                # 计算右侧表达式
                result_value = self.expression_handler.evaluate_expression(expr_str)
                # 更新所有目标变量
                for target in targets:
                    self.expression_handler.variables[target] = result_value

                # 返回赋值结果
                return Result(
                    self.format_assignment_result(targets, result_value), True
                )

            except Exception as e:
                return Result(e, False)
        else:
            # 处理普通表达式
            try:
                result_value = self.expression_handler.evaluate_expression(expression)
                return Result(result_value, True)
            except Exception as e:
                return Result(e, False)

    def format_assignment_result(self, targets: list, result) -> str:
        """格式化赋值结果"""
        if len(targets) == 1:
            return f"{targets[0]} = {result}"
        else:
            return f"{', '.join(targets)} = {result}"

    def list_variables(self) -> dict:
        """返回变量字典的副本"""
        return self.expression_handler.variables.copy()

    def generate_var_name(self) -> str:
        base_name = "new_var"
        counter = 1

        existing_vars = self.list_variables().keys()

        # 生成唯一的变量名
        while True:
            new_name = f"{base_name}_{counter}"
            if new_name not in existing_vars:
                return new_name
            counter += 1

    def judge_var_name(self, var_name: str) -> bool:
        """判断变量名是否合法"""
        return self.expression_handler.is_valid_variable_name(var_name)

    def add_variable(self, var_name: str, expression: str) -> Result:
        """添加或更新变量"""
        if self.expression_handler.is_assignment(f"{var_name} = {expression}"):
            self.expression_handler.variables[var_name] = (
                self.expression_handler.evaluate_expression(expression)
            )
            return Result(f"变量“{var_name}”已添加/更新", True)
        else:
            return Result(f"不合法的变量名“{var_name}”", False)

    def delete_variable(self, var_name) -> Result:
        """删除变量"""
        if var_name in self.expression_handler.variables:
            del self.expression_handler.variables[var_name]
            return Result(f"变量“{var_name}”已删除", True)
        else:
            return Result(f"变量“{var_name}”不存在", False)

    def rename_variable(self, old_name: str, new_name: str) -> Result:
        """重命名变量"""
        if old_name not in self.expression_handler.variables:

            return Result(f"变量“{old_name}”不存在", False)

        if new_name in self.expression_handler.variables:
            return Result(f"变量“{new_name}”已存在", False)

        if not self.expression_handler.is_valid_variable_name(new_name):
            return Result(f"不合法的变量名“{new_name}”", False)

        # 执行重命名操作
        self.expression_handler.variables[new_name] = self.expression_handler.variables[
            old_name
        ]
        del self.expression_handler.variables[old_name]
        return Result(f"已重命名变量“{old_name}”为“{new_name}”", True)
