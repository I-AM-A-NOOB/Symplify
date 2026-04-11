# coding: utf-8
"""Mathematical plotting toolbar component.

This module provides MathPlotToolbar, a Fluent-styled toolbar for
controlling the math plot canvas.

Example:
    >>> from app.qfluentplus.components.math.plot_toolbar import MathPlotToolbar
    >>> from app.qfluentplus.components.math.plot_canvas import MathPlotCanvas
    >>> canvas = MathPlotCanvas()
    >>> toolbar = MathPlotToolbar(canvas)
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSpacerItem, QSizePolicy

from qfluentwidgets import (
    FluentIcon,
    TransparentToolButton,
    TransparentToggleToolButton,
    ToolTipFilter,
    ToolTipPosition,
)

from .plot_canvas import MathPlotCanvas


class MathPlotToolbar(QWidget):
    """Fluent-styled toolbar for MathPlotWidget.

    A custom toolbar that provides navigation controls for the math plot canvas,
    designed with QFluentWidgets styling. Replaces the default matplotlib
    NavigationToolbar with a more integrated Fluent design.

    Attributes:
        canvas (MathPlotCanvas): The associated canvas for navigation.

    Example:
        >>> toolbar = MathPlotToolbar(canvas)
        >>> layout.addWidget(toolbar)
    """

    def __init__(self, canvas: MathPlotCanvas, parent: Optional[QWidget] = None):
        """Initialize the math plot toolbar.

        Args:
            canvas: The MathPlotCanvas to control.
            parent: The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.canvas = canvas
        self._setup_ui()
        self._setup_interactions()

    def _setup_ui(self):
        """Set up the toolbar user interface."""
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 4, 8, 4)
        self.layout.setSpacing(4)

        # Home button - reset to original view
        self.home_btn = TransparentToolButton(FluentIcon.HOME, self)
        self.home_btn.setToolTip("Reset to original view (Home)")
        self.home_btn.installEventFilter(
            ToolTipFilter(self.home_btn, 300, ToolTipPosition.TOP)
        )
        self.home_btn.clicked.connect(self._on_home)
        self.layout.addWidget(self.home_btn)

        # Back button - previous view
        self.back_btn = TransparentToolButton(FluentIcon.LEFT_ARROW, self)
        self.back_btn.setToolTip("Back to previous view")
        self.back_btn.installEventFilter(
            ToolTipFilter(self.back_btn, 300, ToolTipPosition.TOP)
        )
        self.back_btn.clicked.connect(self._on_back)
        self.layout.addWidget(self.back_btn)

        # Forward button - next view
        self.forward_btn = TransparentToolButton(FluentIcon.RIGHT_ARROW, self)
        self.forward_btn.setToolTip("Forward to next view")
        self.forward_btn.installEventFilter(
            ToolTipFilter(self.forward_btn, 300, ToolTipPosition.TOP)
        )
        self.forward_btn.clicked.connect(self._on_forward)
        self.layout.addWidget(self.forward_btn)

        # Separator
        self.layout.addSpacing(8)

        # Pan button - move around (Toggle button)
        self.pan_btn = TransparentToggleToolButton(FluentIcon.MOVE, self)
        self.pan_btn.setToolTip("Pan axes with left mouse")
        self.pan_btn.installEventFilter(
            ToolTipFilter(self.pan_btn, 300, ToolTipPosition.TOP)
        )
        self.pan_btn.clicked.connect(self._on_pan)
        self.layout.addWidget(self.pan_btn)

        # Zoom button - rectangle zoom (Toggle button)
        self.zoom_btn = TransparentToggleToolButton(FluentIcon.ZOOM, self)
        self.zoom_btn.setToolTip("Zoom: Left drag = zoom in, Right drag = zoom out")
        self.zoom_btn.installEventFilter(
            ToolTipFilter(self.zoom_btn, 300, ToolTipPosition.TOP)
        )
        self.zoom_btn.clicked.connect(self._on_zoom)
        self.layout.addWidget(self.zoom_btn)

        # Separator
        self.layout.addSpacing(8)

        # Save button - save figure
        self.save_btn = TransparentToolButton(FluentIcon.SAVE, self)
        self.save_btn.setToolTip("Save the figure")
        self.save_btn.installEventFilter(
            ToolTipFilter(self.save_btn, 300, ToolTipPosition.TOP)
        )
        self.save_btn.clicked.connect(self._on_save)
        self.layout.addWidget(self.save_btn)

        # Spacer
        self.layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # Store view history for back/forward functionality
        self._view_history = []
        self._current_view_index = -1
        self._max_history = 50

        # Interaction state
        self._pan_mode = False
        self._zoom_mode = False
        self._pan_start = None
        self._zoom_start = None
        self._zoom_rect = None
        self._zoom_direction = (
            "in"  # "in" for zoom in (left), "out" for zoom out (right)
        )

        # Save initial view when canvas is ready
        self._initial_view_saved = False

    def _ensure_initial_view(self):
        """Save the initial view if not already saved.

        This should be called after the first plot is rendered.
        """
        if not self._initial_view_saved and self.canvas.axes.has_data():
            self._push_current_view()
            self._initial_view_saved = True

    def _setup_interactions(self):
        """Set up mouse interactions for pan and zoom."""
        # Connect matplotlib events
        self.canvas.mpl_connect("button_press_event", self._on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self._on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)

    def _get_current_view(self):
        """Get the current axes view limits.

        Returns:
            Tuple of (xlim, ylim) representing current view.
        """
        ax = self.canvas.axes
        return (ax.get_xlim(), ax.get_ylim())

    def _set_view(self, view):
        """Set the axes view limits.

        Args:
            view: Tuple of (xlim, ylim).
        """
        xlim, ylim = view
        ax = self.canvas.axes
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        self.canvas.draw()

    def _push_current_view(self):
        """Push current view to history.

        Avoids adding duplicate consecutive views.
        """
        view = self._get_current_view()

        # Don't add if it's the same as the current view
        if self._current_view_index >= 0:
            current_view = self._view_history[self._current_view_index]
            if self._views_equal(view, current_view):
                return

        # If not at end of history, truncate
        if self._current_view_index < len(self._view_history) - 1:
            self._view_history = self._view_history[: self._current_view_index + 1]

        # Add new view
        self._view_history.append(view)

        # Limit history size
        if len(self._view_history) > self._max_history:
            self._view_history.pop(0)
        else:
            self._current_view_index += 1

    def _views_equal(self, view1, view2, tolerance=1e-10):
        """Check if two views are approximately equal.

        Args:
            view1: First view tuple (xlim, ylim).
            view2: Second view tuple (xlim, ylim).
            tolerance: Floating point comparison tolerance.

        Returns:
            True if views are approximately equal.
        """
        (xlim1, ylim1) = view1
        (xlim2, ylim2) = view2

        return (
            abs(xlim1[0] - xlim2[0]) < tolerance
            and abs(xlim1[1] - xlim2[1]) < tolerance
            and abs(ylim1[0] - ylim2[0]) < tolerance
            and abs(ylim1[1] - ylim2[1]) < tolerance
        )

    def _on_mouse_press(self, event):
        """Handle mouse press event.

        Supports:
        - Left button (button 1): Zoom in to rectangle
        - Right button (button 3): Zoom out from rectangle

        Args:
            event: Matplotlib mouse event.
        """
        if event.inaxes != self.canvas.axes:
            return

        if event.button == 1:  # Left button - zoom in
            if self._pan_mode:
                # Ensure initial view is saved before starting pan
                self._ensure_initial_view()
                self._pan_start = (event.xdata, event.ydata)
                self.canvas.setCursor(Qt.CursorShape.ClosedHandCursor)
            elif self._zoom_mode:
                # Ensure initial view is saved before starting zoom
                self._ensure_initial_view()
                self._zoom_start = (event.xdata, event.ydata)
                self._zoom_direction = "in"
                # Create rectangle patch for zoom visual feedback
                from matplotlib.patches import Rectangle

                self._zoom_rect = Rectangle(
                    (event.xdata, event.ydata),
                    0,
                    0,
                    fill=False,
                    edgecolor="red",
                    linestyle="--",
                    linewidth=1,
                )
                self.canvas.axes.add_patch(self._zoom_rect)

        elif event.button == 3:  # Right button - zoom out
            if self._zoom_mode:
                # Ensure initial view is saved before starting zoom
                self._ensure_initial_view()
                self._zoom_start = (event.xdata, event.ydata)
                self._zoom_direction = "out"
                # Create rectangle patch for zoom out visual feedback
                from matplotlib.patches import Rectangle

                self._zoom_rect = Rectangle(
                    (event.xdata, event.ydata),
                    0,
                    0,
                    fill=False,
                    edgecolor="blue",  # Blue for zoom out
                    linestyle="--",
                    linewidth=1,
                )
                self.canvas.axes.add_patch(self._zoom_rect)

    def _on_mouse_release(self, event):
        """Handle mouse release event.

        Supports:
        - Left button release: End pan or zoom in
        - Right button release: Zoom out

        Args:
            event: Matplotlib mouse event.
        """
        # Handle pan mode (left button only)
        if event.button == 1 and self._pan_mode and self._pan_start is not None:
            # End pan
            self._pan_start = None
            self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
            self._push_current_view()
            return

        # Handle zoom mode (left or right button)
        if event.button in [1, 3] and self._zoom_mode and self._zoom_start is not None:
            self._perform_zoom(event)

    def _perform_zoom(self, event):
        """Perform zoom operation based on direction.

        Left button (button 1): Zoom in to selected rectangle
        Right button (button 3): Zoom out, expanding view

        Args:
            event: Matplotlib mouse event.
        """
        if event.inaxes != self.canvas.axes:
            # Remove rectangle even if released outside axes
            if self._zoom_rect:
                self._zoom_rect.remove()
                self._zoom_rect = None
                self.canvas.draw()
            self._zoom_start = None
            return

        x0, y0 = self._zoom_start
        x1, y1 = event.xdata, event.ydata

        # Remove zoom rectangle
        if self._zoom_rect:
            self._zoom_rect.remove()
            self._zoom_rect = None

        # Calculate rectangle dimensions
        x_min, x_max = min(x0, x1), max(x0, x1)
        y_min, y_max = min(y0, y1), max(y0, y1)

        # Only zoom if rectangle is large enough (at least 5 pixels equivalent)
        ax = self.canvas.axes
        bbox = ax.get_window_extent()
        x_scale = (ax.get_xlim()[1] - ax.get_xlim()[0]) / bbox.width
        y_scale = (ax.get_ylim()[1] - ax.get_ylim()[0]) / bbox.height

        x_pixels = abs(x_max - x_min) / x_scale
        y_pixels = abs(y_max - y_min) / y_scale

        if x_pixels < 5 and y_pixels < 5:
            # Too small, cancel zoom
            self.canvas.draw()
            self._zoom_start = None
            return

        if self._zoom_direction == "in":
            # Zoom in: Set limits to selected rectangle
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(y_min, y_max)
        else:
            # Zoom out: Expand current view to include rectangle proportionally
            self._zoom_out(x0, y0, x1, y1)

        self.canvas.draw()
        self._push_current_view()
        self._zoom_start = None

    def _zoom_out(self, x0, y0, x1, y1):
        """Zoom out by expanding the view.

        The amount of zoom out is determined by the rectangle size relative
        to the current view. A larger rectangle = zoom out more.

        Args:
            x0, y0: Start coordinates
            x1, y1: End coordinates
        """
        ax = self.canvas.axes
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()

        # Calculate rectangle center and size
        rect_x_center = (x0 + x1) / 2
        rect_y_center = (y0 + y1) / 2
        rect_x_size = abs(x1 - x0)
        rect_y_size = abs(y1 - y0)

        # Calculate current view size
        view_x_size = cur_xlim[1] - cur_xlim[0]
        view_y_size = cur_ylim[1] - cur_ylim[0]

        # Calculate zoom out factor based on rectangle relative size
        # If rectangle is half the view, zoom out by factor of 2
        if rect_x_size > 0 and rect_y_size > 0:
            factor_x = view_x_size / rect_x_size
            factor_y = view_y_size / rect_y_size
            factor = min(factor_x, factor_y)  # Use smaller factor to maintain aspect
            factor = max(factor, 1.5)  # At least 1.5x zoom out
            factor = min(factor, 5.0)  # At most 5x zoom out
        else:
            factor = 2.0  # Default zoom out factor

        # Calculate new limits centered on the rectangle center
        new_x_size = view_x_size * factor
        new_y_size = view_y_size * factor

        new_xlim = (rect_x_center - new_x_size / 2, rect_x_center + new_x_size / 2)
        new_ylim = (rect_y_center - new_y_size / 2, rect_y_center + new_y_size / 2)

        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)

    def _on_mouse_move(self, event):
        """Handle mouse move event.

        Args:
            event: Matplotlib mouse event.
        """
        if event.inaxes != self.canvas.axes:
            return

        if self._pan_mode and self._pan_start is not None:
            # Perform pan
            x0, y0 = self._pan_start
            x1, y1 = event.xdata, event.ydata

            if x1 is not None and y1 is not None:
                ax = self.canvas.axes
                xlim = ax.get_xlim()
                ylim = ax.get_ylim()

                # Calculate shift
                dx = x0 - x1
                dy = y0 - y1

                # Apply shift
                ax.set_xlim(xlim[0] + dx, xlim[1] + dx)
                ax.set_ylim(ylim[0] + dy, ylim[1] + dy)
                self.canvas.draw()

        elif (
            self._zoom_mode
            and self._zoom_start is not None
            and self._zoom_rect is not None
        ):
            # Update zoom rectangle
            x0, y0 = self._zoom_start
            x1, y1 = event.xdata, event.ydata

            if x1 is not None and y1 is not None:
                width = x1 - x0
                height = y1 - y0
                self._zoom_rect.set_width(width)
                self._zoom_rect.set_height(height)
                self.canvas.draw()

    def _on_scroll(self, event):
        """Handle scroll event for zooming.

        Args:
            event: Matplotlib scroll event.
        """
        if event.inaxes != self.canvas.axes:
            return

        # Get current limits
        ax = self.canvas.axes
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Calculate zoom factor
        if event.button == "up":
            factor = 0.9  # Zoom in
        else:
            factor = 1.1  # Zoom out

        # Get mouse position in data coordinates
        x, y = event.xdata, event.ydata

        if x is not None and y is not None:
            # Calculate new limits centered on mouse position
            new_xlim = (x - (x - xlim[0]) * factor, x + (xlim[1] - x) * factor)
            new_ylim = (y - (y - ylim[0]) * factor, y + (ylim[1] - y) * factor)

            ax.set_xlim(new_xlim)
            ax.set_ylim(new_ylim)
            self.canvas.draw()
            self._push_current_view()

    def _on_home(self):
        """Reset to original/home view.

        Autoscales the axes to fit all data and saves the view to history.
        """
        # Ensure initial view is saved first
        self._ensure_initial_view()

        self.canvas.axes.autoscale()
        self.canvas.draw()
        self._push_current_view()

    def _on_back(self):
        """Go back to previous view.

        Navigates to the previous view in the history stack.
        If already at the first view, does nothing.
        """
        # Ensure initial view is saved
        self._ensure_initial_view()

        if self._current_view_index > 0:
            self._current_view_index -= 1
            view = self._view_history[self._current_view_index]
            self._set_view(view)

    def _on_forward(self):
        """Go forward to next view.

        Navigates to the next view in the history stack.
        If already at the most recent view, does nothing.
        """
        # Ensure initial view is saved
        self._ensure_initial_view()

        if self._current_view_index < len(self._view_history) - 1:
            self._current_view_index += 1
            view = self._view_history[self._current_view_index]
            self._set_view(view)

    def _on_pan(self, checked: bool):
        """Toggle pan mode.

        Args:
            checked: Whether pan mode is enabled.
        """
        self._pan_mode = checked
        if checked:
            self.zoom_btn.setChecked(False)
            self._zoom_mode = False
            self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)

    def _on_zoom(self, checked: bool):
        """Toggle zoom mode.

        Args:
            checked: Whether zoom mode is enabled.
        """
        self._zoom_mode = checked
        if checked:
            self.pan_btn.setChecked(False)
            self._pan_mode = False
            self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)

    def _on_save(self):
        """Save the figure to file."""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Figure",
            "",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)",
        )

        if file_path:
            self.canvas.fig.savefig(file_path, dpi=300, bbox_inches="tight")
