# coding: utf-8
"""Calculator model for symbolic computation.

This module provides the core calculation functionality using SymPy,
completely separate from the view layer. Handles expression evaluation,
plotting, and LaTeX generation.

Example:
    >>> from app.model.calculator import Calculator
    >>> calc = Calculator()
    >>> result = calc.evaluate("x**2 + 2*x + 1")
    >>> print(result.value)
    x**2 + 2*x + 1
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, Optional, Tuple, Union

import sympy as sp
from sympy import Expr, Symbol, latex, sympify
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication,
    parse_expr,
    standard_transformations,
)

# Import PlotData from plot_model for re-export
from app.model.plot import PlotData


class ResultType(Enum):
    """Type of calculation result.

    Attributes:
        EXPRESSION: Mathematical expression result.
        ASSIGNMENT: Variable assignment result.
        PLOT: Plot/graph result.
        ERROR: Error result.
    """

    EXPRESSION = auto()
    ASSIGNMENT = auto()
    PLOT = auto()
    ERROR = auto()


@dataclass
class CalculationResult:
    """Result of a calculation.

    Attributes:
        success: Whether the calculation succeeded.
        result_type: Type of the result.
        value: The result value (SymPy object, None for plot).
        latex: LaTeX representation of the result.
        error: Error message if calculation failed.
        metadata: Optional metadata dictionary for additional info.
        plot_data: Optional plot data for visualization.
        data_points: Optional computed data points for rendering.

    Example:
        >>> result = CalculationResult(
        ...     success=True,
        ...     result_type=ResultType.EXPRESSION,
        ...     value=sp.Symbol('x')**2,
        ...     latex="x^{2}"
        ... )
    """

    success: bool
    result_type: ResultType
    value: Optional[Any] = None
    latex: str = ""
    error: str = ""
    metadata: Optional[Dict[str, Any]] = None
    plot_data: Optional[PlotData] = None
    data_points: Optional[Any] = (
        None  # PlotDataPoints, imported as Any to avoid circular import
    )

    def __str__(self) -> str:
        if self.success:
            return str(self.value) if self.value else ""
        return f"Error: {self.error}"


class Calculator:
    """Symbolic calculator model.

    Provides methods for evaluating mathematical expressions,
    generating LaTeX, and creating plots. Independent of any UI.

    Attributes:
        transformations: SymPy parsing transformations.

    Example:
        >>> calc = Calculator()
        >>> result = calc.evaluate("diff(x**2, x)")
        >>> print(result.latex)
        2 x
    """

    def __init__(self):
        """Initialize the calculator."""
        self.transformations = standard_transformations + (
            implicit_multiplication,
            convert_xor,
        )
        self._plot_model = None  # Lazy initialization

    def evaluate(
        self, expression: str, variables: Optional[Dict[str, Any]] = None
    ) -> CalculationResult:
        """Evaluate a mathematical expression.

        Args:
            expression: The expression to evaluate.
            variables: Optional dictionary of variable values.

        Returns:
            CalculationResult containing the result or error.

        Example:
            >>> calc = Calculator()
            >>> result = calc.evaluate("sin(pi/2)")
            >>> print(result.value)
            1
        """
        try:
            # Ensure variables is a dict
            local_dict = variables if isinstance(variables, dict) else {}

            # Parse the expression
            parsed = parse_expr(
                expression, transformations=self.transformations, local_dict=local_dict
            )

            # Generate LaTeX
            latex_str = latex(parsed)

            return CalculationResult(
                success=True,
                result_type=ResultType.EXPRESSION,
                value=parsed,
                latex=latex_str,
            )

        except Exception as e:
            return CalculationResult(
                success=False, result_type=ResultType.ERROR, error=str(e)
            )

    def evaluate_assignment(
        self, expression: str, variables: Optional[Dict[str, Any]] = None
    ) -> CalculationResult:
        """Evaluate an assignment expression.

        Args:
            expression: Assignment expression like "x = 2 + 2".
            variables: Optional dictionary of existing variables.

        Returns:
            CalculationResult with assignment metadata.

        Example:
            >>> calc = Calculator()
            >>> result = calc.evaluate_assignment("x = 2 + 2")
            >>> print(result.metadata.get("variable_name"), result.value)
            x 4
        """
        try:
            # Split assignment
            if "=" not in expression:
                raise ValueError("Assignment expression must contain '='")

            parts = expression.split("=", 1)
            var_name = parts[0].strip()
            expr_str = parts[1].strip()

            # Evaluate the expression
            expr_result = self.evaluate(expr_str, variables)

            if not expr_result.success:
                return expr_result

            # Create assignment result with metadata
            return CalculationResult(
                success=True,
                result_type=ResultType.ASSIGNMENT,
                value=expr_result.value,
                latex=expr_result.latex,
                metadata={
                    "variable_name": var_name,
                    "variable_value": expr_result.value,
                },
            )

        except Exception as e:
            return CalculationResult(
                success=False, result_type=ResultType.ERROR, error=str(e)
            )

    def get_latex(self, expression: str) -> str:
        """Get LaTeX representation of an expression.

        Args:
            expression: The expression to convert.

        Returns:
            LaTeX string.

        Example:
            >>> calc = Calculator()
            >>> latex = calc.get_latex("x**2 + 1/x")
            >>> print(latex)
            x^{2} + \\frac{1}{x}
        """
        try:
            parsed = parse_expr(expression, transformations=self.transformations)
            return latex(parsed)
        except Exception:
            return ""

    def create_plot_data(
        self,
        value: Any,
        default_range: Tuple[float, float] = (-10, 10),
    ) -> Optional[PlotData]:
        """Create plot data from a calculation result value.

        Analyzes the value to determine if it's a constant or function,
        and creates appropriate PlotData for visualization.

        Args:
            value: The calculation result value (SymPy expression or number).
            default_range: Default (x_min, x_max) for plotting. Defaults to (-10, 10).

        Returns:
            PlotData object or None if value cannot be plotted.

        Example:
            >>> calc = Calculator()
            >>> result = calc.evaluate("sin(x)")
            >>> plot_data = calc.create_plot_data(result.value)
            >>> print(plot_data.is_constant)
            False
        """
        try:
            x_min, x_max = default_range

            # Handle SymPy expressions
            if isinstance(value, Expr):
                free_symbols = list(value.free_symbols)

                if free_symbols:
                    # Function with variables - use first symbol
                    var = free_symbols[0]
                    return PlotData(
                        expr=value,
                        var=var,
                        x_min=x_min,
                        x_max=x_max,
                        is_constant=False,
                        title=f"Plot of ${latex(value)}$",
                    )
                else:
                    # Constant expression (no free symbols)
                    x = Symbol("x")
                    return PlotData(
                        expr=value,
                        var=x,
                        x_min=x_min,
                        x_max=x_max,
                        is_constant=True,
                        title=f"y = ${latex(value)}$",
                    )

            # Handle numeric types
            elif isinstance(value, (int, float)):
                x = Symbol("x")
                return PlotData(
                    expr=float(value),
                    var=x,
                    x_min=x_min,
                    x_max=x_max,
                    is_constant=True,
                    title=f"y = {value}",
                )

            # Cannot plot this type
            return None

        except Exception:
            return None

    def get_plot_model(self):
        """Get or create the PlotModel instance.

        Returns:
            PlotModel instance for computing plot data.
        """
        if self._plot_model is None:
            from .plot import PlotModel

            self._plot_model = PlotModel()
        return self._plot_model
