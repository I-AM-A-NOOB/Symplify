import ast
import keyword
from typing import Any, Dict, List, Tuple, Union

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication,
    parse_expr,
    standard_transformations,
)


class Result:
    """计算结果封装类"""
    
    def __init__(self, content: Union[str, Any], is_success: bool = False):
        """
        初始化结果对象
        
        Args:
            content: 结果内容，可以是字符串或其他类型
            is_success: 是否成功执行，默认为False
        """
        self.content = content
        self.is_success_flag = is_success

    def __str__(self) -> str:
        """返回结果的字符串表示"""
        return str(self.content)

    def is_success(self) -> bool:
        """
        检查计算是否成功
        
        Returns:
            bool: 如果计算成功返回True，否则返回False
        """
        return self.is_success_flag

    def is_error(self) -> bool:
        """
        检查计算是否出错
        
        Returns:
            bool: 如果计算出错返回True，否则返回False
        """
        return not self.is_success_flag


class ExpressionHandler:
    """表达式处理核心类，统一处理赋值和计算逻辑"""

    def __init__(self):
        """初始化表达式处理器"""
        self.variables: Dict[str, Any] = {}  # 存储用户定义的变量
        self.transformations = standard_transformations + (
            implicit_multiplication,
            convert_xor,
        )

    def is_valid_variable_name(self, name: str) -> bool:
        """
        检查变量名是否合法
        
        Args:
            name: 待检查的变量名
            
        Returns:
            bool: 如果变量名合法返回True，否则返回False
        """
        # 使用更直接的方式检查变量名是否合法
        if not name or not isinstance(name, str):
            return False

        # 变量名必须以字母或下划线开头
        if not (name[0].isalpha() or name[0] == "_"):
            return False

        # 其余字符必须是字母、数字或下划线
        for char in name[1:]:
            if not (char.isalnum() or char == "_"):
                return False

        # 检查是否是Python关键字
        if keyword.iskeyword(name):
            return False

        return True

    def is_variable_existing(self, name: str) -> bool:
        """
        检查变量是否已存在
        
        Args:
            name: 变量名
            
        Returns:
            bool: 如果变量已存在返回True，否则返回False
        """
        return name in self.variables

    def is_assignment(self, expression: str) -> bool:
        """
        使用AST判断输入是否为赋值语句
        
        Args:
            expression: 待检查的表达式字符串
            
        Returns:
            bool: 如果是赋值语句返回True，否则返回False
        """
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

    def parse_assignment(self, expression: str) -> Tuple[List[str], str]:
        """
        解析赋值语句，提取变量名和表达式
        
        Args:
            expression: 赋值语句字符串
            
        Returns:
            tuple: 包含变量名列表和表达式字符串的元组
            
        Raises:
            TypeError: 当赋值目标类型不支持时
            NameError: 当增强赋值中变量未定义时
            ValueError: 当操作符不支持时
        """

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
                    raise TypeError(
                        f"Unsupported assignment target type: {type(target).__name__}"
                    )
            expr_str = ast.get_source_segment(expression, node.value)
            return targets, expr_str

        # 处理增强赋值
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                target = node.target.id

                # 检查变量是否已存在（增强赋值必须操作已存在的变量）
                if target not in self.variables:
                    raise NameError(f"name '{target}' is not defined")

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
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")

                right_expr = ast.get_source_segment(expression, node.value)

                # 构建完整表达式
                expr_str = f"{target} {op_char} ({right_expr})"
                return [target], expr_str
            else:
                raise TypeError("Augmented assignment target must be a simple variable")

        else:
            raise TypeError("Unsupported assignment statement type")

    def evaluate_expression(self, expression: str) -> Any:
        """
        计算表达式并返回结果
        
        Args:
            expression: 待计算的表达式字符串
            
        Returns:
            Any: 表达式的计算结果
        """

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
        """初始化符号计算器"""
        self.expression_handler = ExpressionHandler()

    def process_expression(self, expression: str) -> Result:
        """
        计算表达式并返回结果或错误信息
        
        Args:
            expression: 待处理的表达式字符串
            
        Returns:
            Result: 包含计算结果或错误信息的Result对象
        """
        # 检查是否为赋值语句
        if self.expression_handler.is_assignment(expression):
            try:
                # 解析赋值语句
                targets, expr_str = self.expression_handler.parse_assignment(expression)

                # 在执行赋值前，验证所有目标变量名是否合法
                for target in targets:
                    if not self.expression_handler.is_valid_variable_name(target):
                        raise NameError(f"Invalid variable name: '{target}'")

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

    def format_assignment_result(self, targets: List[str], result: Any) -> str:
        """
        格式化赋值结果
        
        Args:
            targets: 变量名列表
            result: 计算结果
            
        Returns:
            str: 格式化后的赋值结果字符串
        """
        if len(targets) == 1:
            return f"{targets[0]} = {result}"
        else:
            return f"{', '.join(targets)} = {result}"

    def list_variables(self) -> Dict[str, Any]:
        """
        返回变量字典的副本
        
        Returns:
            dict: 当前所有变量的副本字典
        """
        return self.expression_handler.variables.copy()

    def generate_var_name(self) -> str:
        """
        生成新的变量名
        
        Returns:
            str: 新的唯一变量名
        """
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
        """
        判断变量名是否合法
        
        Args:
            var_name: 待检查的变量名
            
        Returns:
            bool: 如果变量名合法返回True，否则返回False
        """
        return self.expression_handler.is_valid_variable_name(var_name)

    def add_variable(self, var_name: str, expression: str) -> Result:
        """
        添加或更新变量
        
        Args:
            var_name: 变量名
            expression: 表达式字符串
            
        Returns:
            Result: 操作结果
        """
        # 首先检查变量名是否合法

        if self.expression_handler.is_variable_existing(var_name):
            return Result(f'Variable "{var_name}" already exists', False)
        if not self.expression_handler.is_valid_variable_name(var_name):
            return Result(f'Invalid variable name "{var_name}"', False)

        # 然后尝试计算表达式值
        try:
            # 直接计算表达式值，不检查是否为赋值语句
            evaluated_value = self.expression_handler.evaluate_expression(expression)
            self.expression_handler.variables[var_name] = evaluated_value
            return Result(f'Variable "{var_name}" added/updated', True)
        except Exception as e:
            return Result(f"Expression evaluation error: {str(e)}", False)

    def delete_variable(self, var_name: str) -> Result:
        """
        删除变量
        
        Args:
            var_name: 待删除的变量名
            
        Returns:
            Result: 操作结果
        """
        if self.expression_handler.is_variable_existing(var_name):
            del self.expression_handler.variables[var_name]
            return Result(f'Variable "{var_name}" deleted', True)
        else:
            return Result(f'Variable "{var_name}" does not exist', False)

    def rename_variable(self, old_name: str, new_name: str) -> Result:
        """
        重命名变量
        
        Args:
            old_name: 原变量名
            new_name: 新变量名
            
        Returns:
            Result: 操作结果
        """
        # 首先检查新变量名是否合法（最重要的检查，防止操作后才发现不合法）

        if not self.expression_handler.is_valid_variable_name(new_name):
            return Result(f'Invalid variable name "{new_name}"', False)

        # 然后检查旧变量名是否存在
        if not self.expression_handler.is_variable_existing(old_name):
            return Result(f'Variable "{old_name}" does not exist', False)

        # 检查新变量名是否已存在
        if self.expression_handler.is_variable_existing(new_name):
            return Result(f'Variable "{new_name}" already exists', False)

        # 执行重命名操作
        self.expression_handler.variables[new_name] = self.expression_handler.variables[
            old_name
        ]
        del self.expression_handler.variables[old_name]
        return Result(f'Variable "{old_name}" renamed to "{new_name}"', True)