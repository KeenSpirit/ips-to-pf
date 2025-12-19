"""
UI package for IPS to PowerFactory settings transfer.

This package provides user interface components including:
- Device selection dialog for choosing which devices to update
- Reusable widgets (scrollable frames, etc.)
- UI utility functions

Modules:
    device_selection: Device selection dialog
    widgets: Reusable Tkinter widgets
    utils: UI utility functions
    constants: UI-related constants

Primary Usage:
    from ui import user_selection

    # Show device selection dialog
    selections = user_selection(app, device_dict)
    if selections is None:
        print("User cancelled")
    elif selections == "Batch":
        print("Update all devices")
    else:
        print(f"Selected: {selections}")

Advanced Usage:
    from ui.widgets import VerticalScrolledFrame
    from ui.utils import center_window, create_ok_cancel_buttons
    from ui.constants import WINDOW_TITLE, PADDING_FRAME
"""

# Primary entry point - most users only need this
from ui.device_selection import user_selection

# Dialog class for advanced usage
from ui.device_selection import DeviceSelectionDialog, DeviceSelection

# Reusable widgets
from ui.widgets import VerticalScrolledFrame

# Utility functions
from ui.utils import (
    center_window,
    get_screen_center,
    create_ok_cancel_buttons,
    bind_dialog_keys,
    set_window_topmost,
    disable_resize,
    set_all_children_state,
    create_labeled_frame,
    get_selected_checkboxes,
    set_all_checkboxes,
)

# Constants (for customization)
from ui.constants import (
    WINDOW_TITLE,
    WINDOW_Y_OFFSET,
    WINDOW_TOPMOST,
    RADIO_BATCH_LABEL,
    RADIO_SELECT_LABEL,
    STATE_ON,
    STATE_OFF,
    RETURN_BATCH,
    PADDING_FRAME,
    PADDING_BUTTON,
)

__all__ = [
    # Primary entry point
    "user_selection",
    # Dialog classes
    "DeviceSelectionDialog",
    "DeviceSelection",  # Backward compatibility alias
    # Widgets
    "VerticalScrolledFrame",
    # Utilities
    "center_window",
    "get_screen_center",
    "create_ok_cancel_buttons",
    "bind_dialog_keys",
    "set_window_topmost",
    "disable_resize",
    "set_all_children_state",
    "create_labeled_frame",
    "get_selected_checkboxes",
    "set_all_checkboxes",
    # Constants
    "WINDOW_TITLE",
    "WINDOW_Y_OFFSET",
    "WINDOW_TOPMOST",
    "RADIO_BATCH_LABEL",
    "RADIO_SELECT_LABEL",
    "STATE_ON",
    "STATE_OFF",
    "RETURN_BATCH",
    "PADDING_FRAME",
    "PADDING_BUTTON",
]