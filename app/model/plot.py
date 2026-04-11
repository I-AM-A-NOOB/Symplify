# coding: utf-8
"""Plot model for mathematical data computation.

This module provides PlotModel and data classes for plotting.
Handles all mathematical computation for plotting, separate from the UI layer.
Converts symbolic expressions to numerical data ready for rendering.

Example:
    >>> from app.model.plot_model import PlotModel, PlotData
    >>> from sympy import symbols, sin
    >>> x = symbols('x')
    >>> model = PlotModel()
    >>> plot_data = PlotData(sin(x), x, -10, 10, False)
    >>> points = model.compute_plot_data(plot_data)
    >>> print(points.x.shape, points.y.shape)
    (500,) (500,)
"""
from dataclasses import dataclass
from typing import Optional, Tuple, Union

import numpy as np
import sympy as sp
from sympy import Expr, Symbol


@dataclass
class PlotData:
    """Data required for plotting a mathematical expression.

    This class encapsulates all information needed to plot a function,
    including the expression, variable range, and whether it's a constant.

    Attributes:
        expr: The SymPy expression or numeric value to plot.
        var: The variable symbol (for functions) or 'x' (for constants).
        x_min: Minimum x value for plotting.
        x_max: Maximum x value for plotting.
        is_constant: Whether this is a constant value (not a function).
        title: Optional plot title.

    Example:
        >>> from sympy import symbols, sin
        >>> x = symbols('x')
        >>> plot_data = PlotData(sin(x), x, -10, 10, False)
        >>> const_data = PlotData(3.14, x, -10, 10, True)
    """

    expr: Union[Expr, float, int]
    var: Symbol
    x_min: float
    x_max: float
    is_constant: bool
    title: Optional[str] = None

    @property
    def var_range(self) -> Tuple[Symbol, float, float]:
        """Get the variable range as a tuple.

        Returns:
            Tuple of (var, x_min, x_max).
        """
        return (self.var, self.x_min, self.x_max)


@dataclass
class PlotDataPoints:
    """Computed data points ready for plotting.

    Contains the numerical x, y arrays and display labels.
    This is the output of PlotModel computation.

    Attributes:
        x: X-axis values (numpy array).
        y: Y-axis values (numpy array).
        title: Plot title.
        xlabel: X-axis label.
        ylabel: Y-axis label.
        label: Line label for legend.

    Example:
        >>> points = PlotDataPoints(
        ...     x=np.linspace(-10, 10, 500),
        ...     y=np.sin(np.linspace(-10, 10, 500)),
        ...     title="sin(x)",
        ...     xlabel="x",
        ...     ylabel="y",
        ...     label="sin(x)"
        ... )
    """

    x: np.ndarray
    y: np.ndarray
    title: str
    xlabel: str
    ylabel: str
    label: str


class PlotModel:
    """Model for mathematical plotting computation.

    Handles all mathematical operations needed for plotting:
    - Generating x values
    - Computing y values (lambdify for functions, evalf for constants)
    - Data sanitization (shape correction, complex handling)
    - Label generation

    This class is independent of Qt/UI and can be used for:
    - Rendering in widgets
    - Exporting data to files
    - Batch processing

    Attributes:
        _lambdify_cache: Cache for lambdify functions to improve performance.

    Example:
        >>> from sympy import symbols, cos
        >>> x = symbols('x')
        >>> model = PlotModel()
        >>> plot_data = PlotData(cos(x), x, -5, 5, False)
        >>> points = model.compute_plot_data(plot_data)
        >>> # points can now be passed to any plotting widget
    """

    def __init__(self):
        """Initialize the plot model."""
        self._lambdify_cache: dict = {}

    def compute_plot_data(self, plot_data) -> Optional[PlotDataPoints]:
        """Convert PlotData to numerical data points.

        Performs all mathematical computation to transform a symbolic
        PlotData into numerical arrays ready for rendering.

        Args:
            plot_data: PlotData containing expression and range info.

        Returns:
            PlotDataPoints with computed x, y arrays and labels,
            or None if computation fails.

        Example:
            >>> from sympy import symbols, exp
            >>> x = symbols('x')
            >>> model = PlotModel()
            >>> pd = PlotData(exp(x), x, -2, 2, False)
            >>> points = model.compute_plot_data(pd)
            >>> print(f"Range: [{points.y.min():.2f}, {points.y.max():.2f}]")
        """
        if plot_data is None:
            return None

        try:
            # Generate x values
            x_vals = self._generate_x_values(plot_data.x_min, plot_data.x_max)

            # Compute y values
            if plot_data.is_constant:
                y_vals = self._compute_constant(plot_data.expr, x_vals)
            else:
                y_vals = self._compute_function(plot_data.expr, plot_data.var, x_vals)

            # Sanitize data
            y_vals = self._sanitize_data(y_vals, x_vals)

            # Generate labels
            labels = self._generate_labels(plot_data)

            return PlotDataPoints(
                x=x_vals,
                y=y_vals,
                title=labels["title"],
                xlabel=labels["xlabel"],
                ylabel=labels["ylabel"],
                label=labels["label"],
            )

        except Exception:
            # Computation failed, return None
            return None

    def _generate_x_values(
        self, x_min: float, x_max: float, num_points: int = 500
    ) -> np.ndarray:
        """Generate x-axis values.

        Args:
            x_min: Minimum x value.
            x_max: Maximum x value.
            num_points: Number of points to generate. Defaults to 500.

        Returns:
            Array of x values.
        """
        return np.linspace(x_min, x_max, num_points)

    def _compute_constant(
        self, expr: Union[Expr, float, int], x_vals: np.ndarray
    ) -> np.ndarray:
        """Compute y values for a constant expression.

        Args:
            expr: Constant expression or numeric value.
            x_vals: X values (for shape reference).

        Returns:
            Array of constant y values.
        """
        if isinstance(expr, Expr):
            const_val = float(expr.evalf())
        else:
            const_val = float(expr)
        return np.full_like(x_vals, const_val)

    def _compute_function(
        self, expr: Expr, var: Symbol, x_vals: np.ndarray
    ) -> np.ndarray:
        """Compute y values for a function using lambdify.

        Uses caching to avoid recompiling the same function.

        Args:
            expr: SymPy expression to evaluate.
            var: Variable symbol.
            x_vals: X values to evaluate at.

        Returns:
            Array of y values.
        """
        # Create cache key
        cache_key = (id(expr), id(var))

        # Check cache
        if cache_key not in self._lambdify_cache:
            self._lambdify_cache[cache_key] = sp.lambdify(var, expr, "numpy")

        # Evaluate
        f = self._lambdify_cache[cache_key]
        return f(x_vals)

    def _sanitize_data(self, y_vals: np.ndarray, x_vals: np.ndarray) -> np.ndarray:
        """Sanitize computed data.

        Handles:
        - Shape mismatches
        - Complex values
        - Invalid values

        Args:
            y_vals: Computed y values.
            x_vals: Reference x values.

        Returns:
            Sanitized y values.
        """
        y_vals = np.asarray(y_vals)

        # Fix shape mismatch
        if y_vals.shape != x_vals.shape:
            if y_vals.size > 0:
                y_vals = np.full_like(x_vals, y_vals.flat[0])
            else:
                y_vals = np.zeros_like(x_vals)

        # Handle complex values
        if np.iscomplexobj(y_vals):
            y_vals = np.real(y_vals)

        # Handle inf/nan
        y_vals = np.nan_to_num(y_vals, nan=0.0, posinf=1e10, neginf=-1e10)

        return y_vals

    def _generate_labels(self, plot_data) -> dict:
        """Generate display labels for the plot.

        Args:
            plot_data: PlotData with expression info.

        Returns:
            Dictionary with title, xlabel, ylabel, label.
        """
        var_str = str(plot_data.var)

        if plot_data.is_constant:
            title = plot_data.title or f"y = {plot_data.expr}"
            ylabel = "y"
            if isinstance(plot_data.expr, Expr):
                label = f"y = ${sp.latex(plot_data.expr)}$"
            else:
                label = f"y = {plot_data.expr}"
        else:
            title = plot_data.title or f"Plot of ${sp.latex(plot_data.expr)}$"
            ylabel = f"f({var_str})"
            label = f"${sp.latex(plot_data.expr)}$"

        return {
            "title": title,
            "xlabel": var_str,
            "ylabel": ylabel,
            "label": label,
        }

    def compute_parametric_data(
        self,
        expr: Expr,
        param: Symbol,
        t_min: float,
        t_max: float,
        num_points: int = 500,
    ) -> Optional[np.ndarray]:
        """Compute data points for a parametric expression.

        Evaluates a SymPy expression over a parameter range.
        Used for parametric curve plotting (x(t), y(t)).

        Args:
            expr: The SymPy expression to evaluate.
            param: The parameter symbol.
            t_min: Minimum parameter value.
            t_max: Maximum parameter value.
            num_points: Number of points to generate. Defaults to 500.

        Returns:
            Array of computed values, or None if computation fails.

        Example:
            >>> from sympy import symbols, cos, sin
            >>> t = symbols('t')
            >>> model = PlotModel()
            >>> x_data = model.compute_parametric_data(cos(t), t, 0, 2*np.pi)
            >>> y_data = model.compute_parametric_data(sin(t), t, 0, 2*np.pi)
        """
        try:
            # Generate parameter values
            t_vals = np.linspace(t_min, t_max, num_points)

            # Create cache key
            cache_key = (id(expr), id(param))

            # Check cache
            if cache_key not in self._lambdify_cache:
                self._lambdify_cache[cache_key] = sp.lambdify(param, expr, "numpy")

            # Evaluate
            f = self._lambdify_cache[cache_key]
            result = f(t_vals)

            # Sanitize
            result = np.asarray(result, dtype=float)
            if np.iscomplexobj(result):
                result = np.real(result)
            result = np.nan_to_num(result, nan=0.0, posinf=1e10, neginf=-1e10)

            return result

        except Exception:
            return None

    def clear_cache(self) -> None:
        """Clear the lambdify cache.

        Call this when memory usage is a concern or when
        expressions are no longer needed.
        """
        self._lambdify_cache.clear()
