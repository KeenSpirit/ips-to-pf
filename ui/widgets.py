"""
Reusable UI widgets for the IPS to PowerFactory application.

This module contains custom Tkinter widgets that can be reused
across different dialogs and windows.

Classes:
    VerticalScrolledFrame: A frame with vertical scrollbar support
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from ui.constants import SCROLL_FRAME_HEIGHT


class VerticalScrolledFrame(ttk.Frame):
    """
    A Tkinter frame with a vertical scrollbar for scrolling content.

    This widget provides a scrollable container for placing other widgets.
    Use the 'interior' attribute to place widgets inside the scrollable area.

    Attributes:
        interior: The inner frame where child widgets should be placed

    Example:
        >>> root = tk.Tk()
        >>> scrolled = VerticalScrolledFrame(root)
        >>> scrolled.pack(fill=tk.BOTH, expand=True)
        >>> # Add widgets to the interior
        >>> label = ttk.Label(scrolled.interior, text="Hello")
        >>> label.pack()

    Note:
        This frame only supports vertical scrolling. For horizontal
        scrolling, a different implementation would be needed.
    """

    def __init__(
        self,
        parent: tk.Widget,
        height: int = SCROLL_FRAME_HEIGHT,
        **kwargs
    ):
        """
        Initialize the VerticalScrolledFrame.

        Args:
            parent: The parent widget
            height: Height of the scrollable area in pixels
            **kwargs: Additional arguments passed to ttk.Frame
        """
        super().__init__(parent, **kwargs)

        # Create canvas and scrollbar
        self._scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self._scrollbar.pack(fill=tk.Y, side=tk.RIGHT, expand=False)

        self._canvas = tk.Canvas(
            self,
            bd=0,
            highlightthickness=0,
            yscrollcommand=self._scrollbar.set,
            height=height
        )
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scrollbar.config(command=self._canvas.yview)

        # Reset the view
        self._canvas.xview_moveto(0)
        self._canvas.yview_moveto(0)

        # Create the interior frame inside the canvas
        self.interior = ttk.Frame(self._canvas)
        self._interior_id = self._canvas.create_window(
            0, 0,
            window=self.interior,
            anchor=tk.NW
        )

        # Bind events for dynamic resizing
        self.interior.bind("<Configure>", self._on_interior_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Bind mouse wheel scrolling
        self._bind_mousewheel()

    def _on_interior_configure(self, event: Optional[tk.Event] = None) -> None:
        """
        Update scrollbar when interior frame size changes.

        Args:
            event: The Configure event (optional)
        """
        # Update the scroll region to encompass the interior frame
        size = (
            self.interior.winfo_reqwidth(),
            self.interior.winfo_reqheight()
        )
        self._canvas.config(scrollregion=f"0 0 {size[0]} {size[1]}")

        # Update canvas width if interior is wider
        if self.interior.winfo_reqwidth() != self._canvas.winfo_width():
            self._canvas.config(width=self.interior.winfo_reqwidth())

    def _on_canvas_configure(self, event: Optional[tk.Event] = None) -> None:
        """
        Update interior frame width when canvas size changes.

        Args:
            event: The Configure event (optional)
        """
        if self.interior.winfo_reqwidth() != self._canvas.winfo_width():
            self._canvas.itemconfigure(
                self._interior_id,
                width=self._canvas.winfo_width()
            )

    def _bind_mousewheel(self) -> None:
        """Bind mouse wheel events for scrolling."""
        # Windows and macOS
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        # Linux
        self._canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _on_mousewheel(self, event: tk.Event) -> None:
        """
        Handle mouse wheel scrolling (Windows/macOS).

        Args:
            event: The MouseWheel event
        """
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event: tk.Event) -> None:
        """
        Handle mouse wheel scrolling (Linux).

        Args:
            event: The Button-4 or Button-5 event
        """
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")

    def scroll_to_top(self) -> None:
        """Scroll the view to the top."""
        self._canvas.yview_moveto(0)

    def scroll_to_bottom(self) -> None:
        """Scroll the view to the bottom."""
        self._canvas.yview_moveto(1)

    def get_scroll_position(self) -> float:
        """
        Get the current scroll position.

        Returns:
            Float between 0.0 (top) and 1.0 (bottom)
        """
        return self._canvas.yview()[0]

    def set_scroll_position(self, position: float) -> None:
        """
        Set the scroll position.

        Args:
            position: Float between 0.0 (top) and 1.0 (bottom)
        """
        self._canvas.yview_moveto(position)