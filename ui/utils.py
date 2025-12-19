"""
UI utility functions for the IPS to PowerFactory application.

This module provides helper functions for common UI operations
such as window positioning and widget creation.
"""

import tkinter as tk
from tkinter import ttk
from typing import Tuple, Optional, Callable, Any

from ui.constants import (
    BUTTON_OK,
    BUTTON_CANCEL,
    PADDING_BUTTON,
    KEY_ENTER,
    KEY_ESCAPE,
)


def center_window(
    window: tk.Tk,
    y_offset: int = 0
) -> None:
    """
    Center a window on the screen.

    This function calculates the center position based on screen
    dimensions and the window's requested size, then positions
    the window accordingly.

    Args:
        window: The Tkinter window to center
        y_offset: Vertical offset from center (negative = up, positive = down)

    Example:
        >>> root = tk.Tk()
        >>> root.update_idletasks()  # Ensure geometry is calculated
        >>> center_window(root, y_offset=-100)  # Slightly above center
    """
    # Update to get accurate dimensions
    window.update_idletasks()

    # Calculate center position
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    window_width = window.winfo_reqwidth()
    window_height = window.winfo_reqheight()

    x = int((screen_width - window_width) / 2)
    y = int((screen_height - window_height) / 2) + y_offset

    # Ensure window stays on screen
    x = max(0, x)
    y = max(0, y)

    window.geometry(f"+{x}+{y}")


def get_screen_center(window: tk.Tk) -> Tuple[int, int]:
    """
    Get the center coordinates of the screen.

    Args:
        window: A Tkinter window (used to access screen info)

    Returns:
        Tuple of (x, y) coordinates for screen center
    """
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    return screen_width // 2, screen_height // 2


def create_ok_cancel_buttons(
    parent: tk.Widget,
    ok_callback: Callable[[], Any],
    cancel_callback: Callable[[], Any],
    ok_text: str = BUTTON_OK,
    cancel_text: str = BUTTON_CANCEL,
    padding: int = PADDING_BUTTON
) -> ttk.Frame:
    """
    Create a standard OK/Cancel button frame.

    This creates a frame with horizontally arranged OK and Cancel
    buttons, following a consistent layout pattern.

    Args:
        parent: The parent widget
        ok_callback: Function to call when OK is clicked
        cancel_callback: Function to call when Cancel is clicked
        ok_text: Text for the OK button
        cancel_text: Text for the Cancel button
        padding: Horizontal padding between buttons

    Returns:
        The frame containing the buttons

    Example:
        >>> def on_ok():
        ...     print("OK clicked")
        >>> def on_cancel():
        ...     print("Cancel clicked")
        >>> frame = create_ok_cancel_buttons(root, on_ok, on_cancel)
        >>> frame.pack()
    """
    frame = ttk.Frame(parent)

    ok_button = ttk.Button(frame, text=ok_text, command=ok_callback)
    ok_button.grid(column=0, row=0, padx=padding)

    cancel_button = ttk.Button(frame, text=cancel_text, command=cancel_callback)
    cancel_button.grid(column=1, row=0, padx=padding)

    return frame


def bind_dialog_keys(
    window: tk.Tk,
    ok_callback: Callable[[Optional[tk.Event]], Any],
    cancel_callback: Callable[[Optional[tk.Event]], Any]
) -> None:
    """
    Bind standard keyboard shortcuts to a dialog.

    Binds:
    - Enter/Return key to OK callback
    - Escape key to Cancel callback

    Args:
        window: The dialog window
        ok_callback: Function to call on Enter (accepts optional event)
        cancel_callback: Function to call on Escape (accepts optional event)

    Example:
        >>> bind_dialog_keys(dialog, on_ok, on_cancel)
    """
    window.bind(KEY_ENTER, ok_callback)
    window.bind(KEY_ESCAPE, cancel_callback)


def set_window_topmost(window: tk.Tk, topmost: bool = True) -> None:
    """
    Set whether a window stays on top of other windows.

    Args:
        window: The Tkinter window
        topmost: True to keep on top, False to allow other windows over it
    """
    window.wm_attributes("-topmost", 1 if topmost else 0)


def disable_resize(window: tk.Tk) -> None:
    """
    Disable window resizing.

    Args:
        window: The Tkinter window
    """
    window.resizable(False, False)


def set_all_children_state(
    parent: tk.Widget,
    state: str,
    widget_type: Optional[type] = None
) -> None:
    """
    Set the state of all child widgets.

    Args:
        parent: The parent widget containing children
        state: The state to set (e.g., tk.NORMAL, tk.DISABLED)
        widget_type: Optional filter for specific widget types

    Example:
        >>> # Disable all checkbuttons
        >>> set_all_children_state(frame, tk.DISABLED, ttk.Checkbutton)
        >>> # Enable all children
        >>> set_all_children_state(frame, tk.NORMAL)
    """
    for child in parent.winfo_children():
        if widget_type is None or isinstance(child, widget_type):
            try:
                child.config(state=state)
            except tk.TclError:
                # Widget doesn't support state
                pass


def create_labeled_frame(
    parent: tk.Widget,
    label: str,
    padding: int = PADDING_BUTTON
) -> ttk.LabelFrame:
    """
    Create a labeled frame with consistent styling.

    Args:
        parent: The parent widget
        label: The frame label text
        padding: Internal padding

    Returns:
        The created LabelFrame
    """
    frame = ttk.LabelFrame(parent, text=label, padding=padding)
    return frame


def get_selected_checkboxes(
    variables: dict,
    on_value: str = "On"
) -> list:
    """
    Get list of selected checkbox keys from a variables dictionary.

    Args:
        variables: Dictionary mapping keys to StringVar objects
        on_value: The value indicating a selected state

    Returns:
        List of keys where checkbox is selected

    Example:
        >>> vars = {"item1": var1, "item2": var2}
        >>> selected = get_selected_checkboxes(vars)
        >>> print(selected)  # ["item1"] if item1 is checked
    """
    return [
        key for key, var in variables.items()
        if var.get() == on_value
    ]


def set_all_checkboxes(
    variables: dict,
    value: str
) -> None:
    """
    Set all checkbox variables to the same value.

    Args:
        variables: Dictionary mapping keys to StringVar objects
        value: The value to set (e.g., "On" or "Off")

    Example:
        >>> set_all_checkboxes(checkbox_vars, "On")  # Select all
        >>> set_all_checkboxes(checkbox_vars, "Off")  # Deselect all
    """
    for var in variables.values():
        var.set(value)