# coding: utf-8
"""Symbolic calculation model built on SymPy.

Evaluates expressions and produces LaTeX. Independent of any UI.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, Optional

from sympy import latex
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication,
    parse_expr,
    standard_transformations,
)


class ResultType(Enum):
    """Type of a calculation result.

    Attributes:
        EXPRESSION: Mathematical expression result.
        ASSIGNMENT: Variable assignment result.
        ERROR: Error result.
    """

    EXPRESSION = auto()
    ASSIGNMENT = auto()
    ERROR = auto()


@dataclass
class CalculationResult:
    """Result of a calculation.

    Attributes:
        success: Whether the calculation succeeded.
        result_type: Type of the result.
        value: The result value (a SymPy object), None for errors.
        latex: LaTeX representation of the result.
        error: Error message if the calculation failed.
        metadata: Optional metadata for additional info.
    """

    success: bool
    result_type: ResultType
    value: Optional[Any] = None
    latex: str = ""
    error: str = ""
    metadata: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        if self.success:
            return str(self.value) if self.value else ""
        return f"Error: {self.error}"


class Calculator:
    """Symbolic calculator model.

    Provides expression evaluation and LaTeX generation. Independent of any UI.
    """

    def __init__(self):
        """Initialize the calculator."""
        self.transformations = standard_transformations + (
            implicit_multiplication,
            convert_xor,
        )

    def evaluate(
        self, expression: str, variables: Optional[Dict[str, Any]] = None
    ) -> CalculationResult:
        """Evaluate a mathematical expression.

        Args:
            expression: The expression to evaluate.
            variables: Optional dictionary of existing variable values.

        Returns:
            CalculationResult containing the result or an error.
        """
        try:
            local_dict = variables if isinstance(variables, dict) else {}
            parsed = parse_expr(
                expression, transformations=self.transformations, local_dict=local_dict
            )
            return CalculationResult(
                success=True,
                result_type=ResultType.EXPRESSION,
                value=parsed,
                latex=latex(parsed),
            )
        except Exception as e:
            return CalculationResult(
                success=False, result_type=ResultType.ERROR, error=str(e)
            )
