"""
Device selection dialog for IPS to PowerFactory settings transfer.

This module provides the user interface for selecting which protection
devices should have their settings updated from IPS. Users can either:
- Update all devices (batch mode)
- Select specific devices from a hierarchical tree view

The dialog organizes devices by substation and feeder, allowing
users to select at any level of the hierarchy.

Usage:
    from ui.device_selection import user_selection

    # Show dialog and get user selections
    selections = user_selection(app, device_dict)
    if selections is None:
        print("User cancelled")
    elif selections == "Batch":
        print("Update all devices")
    else:
        print(f"Selected devices: {selections}")
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Any, Union

from ui.constants import (
    WINDOW_TITLE,
    WINDOW_Y_OFFSET,
    WINDOW_TOPMOST,
    RADIO_BATCH_LABEL,
    RADIO_SELECT_LABEL,
    RADIO_VALUE_BATCH,
    RADIO_VALUE_SELECT,
    BUTTON_SELECT_ALL,
    BUTTON_UNSELECT_ALL,
    STATE_ON,
    STATE_OFF,
    RETURN_BATCH,
    PADDING_FRAME,
    PADDING_BUTTON,
    PADDING_CHECKBOX_SUB,
    PADDING_CHECKBOX_FEEDER,
    PADDING_CHECKBOX_DEVICE,
)
from ui.widgets import VerticalScrolledFrame
from ui.utils import (
    center_window,
    bind_dialog_keys,
    set_window_topmost,
    disable_resize,
    set_all_children_state,
    set_all_checkboxes,
    get_selected_checkboxes,
)


def user_selection(
        app: Any,
        device_dict: Dict[str, List]
) -> Optional[Union[str, List[str]]]:
    """
    Present user with a dialog to select devices for update.

    This is the main entry point for the device selection UI. It creates
    and displays the selection dialog, then returns the user's choices.

    Args:
        app: PowerFactory application object (kept for API compatibility)
        device_dict: Dictionary mapping device names to device info lists.
                    Each list contains: [pf_obj, class, phases, feeder, sub]

    Returns:
        - None: User cancelled the dialog
        - "Batch": User selected batch mode (update all devices)
        - List[str]: List of selected device names

    Example:
        >>> devices, device_dict = get_all_protection_devices(app)
        >>> selections = user_selection(app, device_dict)
        >>> if selections == "Batch":
        ...     process_all_devices()
        >>> elif selections:
        ...     for device_name in selections:
        ...         process_device(device_name)
    """
    dialog = DeviceSelectionDialog(device_dict)

    # User cancelled
    if dialog.cancelled:
        return None

    # Batch mode selected
    if dialog.batch_mode:
        return RETURN_BATCH

    # Return list of selected devices
    return get_selected_checkboxes(dialog.device_variables, STATE_ON)


class DeviceSelectionDialog(tk.Tk):
    """
    Dialog for selecting protection devices to update.

    This dialog presents devices in a hierarchical tree structure:
    - Substations (top level)
      - Feeders (mid level)
        - Devices (leaf level, selectable)

    Users can:
    - Select individual devices
    - Select all devices in a feeder
    - Select all devices in a substation
    - Use "Select All" / "Unselect All" buttons
    - Choose batch mode to update all devices

    Attributes:
        cancelled: True if user cancelled the dialog
        batch_mode: True if user selected batch update mode
        device_variables: Dict mapping device names to their checkbox variables
        device_ordered_list: List of device names in display order
    """

    def __init__(self, device_dict: Dict[str, List], **kwargs):
        """
        Initialize the device selection dialog.

        Args:
            device_dict: Dictionary mapping device names to device info
            **kwargs: Additional arguments passed to Tk
        """
        super().__init__(**kwargs)

        # Store device data
        self._device_dict = device_dict

        # Track checkbox variables at each level
        self.device_variables: Dict[str, tk.StringVar] = {}
        self._substation_variables: Dict[str, tk.StringVar] = {}
        self._feeder_variables: Dict[str, tk.StringVar] = {}

        # Track display order
        self.device_ordered_list: List[str] = []

        # Dialog result flags
        self.cancelled = False
        self.batch_mode = False

        # Build the UI
        self._setup_window()
        self._create_widgets()

        # Run the dialog
        self.mainloop()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.title(WINDOW_TITLE)
        disable_resize(self)
        set_window_topmost(self, WINDOW_TOPMOST)
        self.focus_force()

    def _create_widgets(self) -> None:
        """Create all dialog widgets."""
        self._create_radio_buttons()
        self._create_action_buttons()
        self._create_device_list()
        self._create_dialog_buttons()

        # Set initial state (batch mode selected by default)
        self._on_radio_change()

        # Position window after all widgets are created
        center_window(self, WINDOW_Y_OFFSET)

    def _create_radio_buttons(self) -> None:
        """Create the mode selection radio buttons."""
        frame = ttk.Frame(self)
        frame.pack(pady=PADDING_FRAME)

        self._mode_var = tk.StringVar(value=RADIO_VALUE_BATCH)

        # Batch mode radio button
        radio_batch = ttk.Radiobutton(
            frame,
            text=RADIO_BATCH_LABEL,
            variable=self._mode_var,
            value=RADIO_VALUE_BATCH,
            command=self._on_radio_change,
        )
        radio_batch.pack(anchor=tk.W)

        # Selection mode radio button
        radio_select = ttk.Radiobutton(
            frame,
            text=RADIO_SELECT_LABEL,
            variable=self._mode_var,
            value=RADIO_VALUE_SELECT,
            command=self._on_radio_change,
        )
        radio_select.pack(anchor=tk.W)

    def _create_action_buttons(self) -> None:
        """Create Select All / Unselect All buttons."""
        frame = ttk.Frame(self)
        frame.pack(pady=PADDING_BUTTON)

        self._select_all_btn = ttk.Button(
            frame,
            text=BUTTON_SELECT_ALL,
            command=self._select_all,
            state=tk.DISABLED
        )
        self._select_all_btn.grid(column=0, row=0, padx=PADDING_BUTTON)

        self._unselect_all_btn = ttk.Button(
            frame,
            text=BUTTON_UNSELECT_ALL,
            command=self._unselect_all,
            state=tk.DISABLED
        )
        self._unselect_all_btn.grid(column=1, row=0, padx=PADDING_BUTTON)

    def _create_device_list(self) -> None:
        """Create the scrollable device selection list."""
        self._scroll_frame = VerticalScrolledFrame(self)
        self._build_device_tree()
        self._scroll_frame.pack(fill=tk.BOTH, expand=True, pady=PADDING_BUTTON)

        # Set initial state to disabled
        set_all_children_state(
            self._scroll_frame.interior,
            tk.DISABLED,
            ttk.Checkbutton
        )

    def _build_device_tree(self) -> None:
        """Build the hierarchical device tree with checkboxes."""
        interior = self._scroll_frame.interior
        device_list = list(self._device_dict.keys())
        processed_subs: Dict[str, bool] = {}
        processed_feeders: Dict[str, bool] = {}

        for device_name in device_list:
            device_info = self._device_dict[device_name]
            substation = device_info[4]
            feeder = device_info[3]

            # Create substation checkbox if not already created
            if substation not in processed_subs:
                self._create_substation_checkbox(interior, substation, device_list)
                processed_subs[substation] = True

                # Create feeder checkboxes for this substation
                for sub_device in device_list:
                    if self._device_dict[sub_device][4] != substation:
                        continue

                    sub_feeder = self._device_dict[sub_device][3]
                    if sub_feeder not in processed_feeders:
                        self._create_feeder_checkbox(interior, sub_feeder)
                        processed_feeders[sub_feeder] = True

                        # Create device checkboxes for this feeder
                        for feeder_device in device_list:
                            if self._device_dict[feeder_device][3] != sub_feeder:
                                continue
                            if feeder_device not in self.device_variables:
                                self._create_device_checkbox(interior, feeder_device)

    def _create_substation_checkbox(
            self,
            parent: tk.Widget,
            substation: str,
            device_list: List[str]
    ) -> None:
        """Create a substation-level checkbox."""
        var = tk.StringVar()
        self._substation_variables[substation] = var

        checkbox = ttk.Checkbutton(
            parent,
            text=substation,
            variable=var,
            onvalue=STATE_ON,
            offvalue=STATE_OFF,
            command=lambda s=substation: self._on_substation_toggle(s),
        )
        checkbox.pack(anchor=tk.W, padx=PADDING_CHECKBOX_SUB)

    def _create_feeder_checkbox(self, parent: tk.Widget, feeder: str) -> None:
        """Create a feeder-level checkbox."""
        var = tk.StringVar()
        self._feeder_variables[feeder] = var

        checkbox = ttk.Checkbutton(
            parent,
            text=feeder,
            variable=var,
            onvalue=STATE_ON,
            offvalue=STATE_OFF,
            command=lambda f=feeder: self._on_feeder_toggle(f),
        )
        checkbox.pack(anchor=tk.W, padx=PADDING_CHECKBOX_FEEDER)

    def _create_device_checkbox(self, parent: tk.Widget, device_name: str) -> None:
        """Create a device-level checkbox."""
        var = tk.StringVar()
        self.device_variables[device_name] = var
        self.device_ordered_list.append(device_name)

        checkbox = ttk.Checkbutton(
            parent,
            text=device_name,
            variable=var,
            onvalue=STATE_ON,
            offvalue=STATE_OFF,
        )
        checkbox.pack(anchor=tk.W, padx=PADDING_CHECKBOX_DEVICE)

    def _create_dialog_buttons(self) -> None:
        """Create OK and Cancel buttons."""
        frame = ttk.Frame(self)
        frame.pack(pady=PADDING_FRAME)

        ttk.Button(frame, text="OK", command=self._on_ok).grid(
            column=0, row=0, padx=PADDING_BUTTON
        )
        ttk.Button(frame, text="Cancel", command=self._on_cancel).grid(
            column=1, row=0, padx=PADDING_BUTTON
        )

        # Bind keyboard shortcuts
        bind_dialog_keys(self, self._on_ok, self._on_cancel)

    def _on_radio_change(self) -> None:
        """Handle mode radio button selection change."""
        is_select_mode = self._mode_var.get() == RADIO_VALUE_SELECT

        if is_select_mode:
            # Enable selection controls
            self._select_all_btn.config(state=tk.NORMAL)
            self._unselect_all_btn.config(state=tk.NORMAL)
            set_all_children_state(
                self._scroll_frame.interior,
                tk.NORMAL,
                ttk.Checkbutton
            )
        else:
            # Disable selection controls
            self._select_all_btn.config(state=tk.DISABLED)
            self._unselect_all_btn.config(state=tk.DISABLED)
            set_all_children_state(
                self._scroll_frame.interior,
                tk.DISABLED,
                ttk.Checkbutton
            )

    def _on_substation_toggle(self, substation: str) -> None:
        """Handle substation checkbox toggle."""
        state = self._substation_variables[substation].get()
        target_value = STATE_ON if state == STATE_ON else STATE_OFF

        # Toggle all devices and feeders in this substation
        for device_name, device_info in self._device_dict.items():
            if device_info[4] == substation:
                self.device_variables[device_name].set(target_value)
                feeder = device_info[3]
                if feeder in self._feeder_variables:
                    self._feeder_variables[feeder].set(target_value)

    def _on_feeder_toggle(self, feeder: str) -> None:
        """Handle feeder checkbox toggle."""
        state = self._feeder_variables[feeder].get()
        target_value = STATE_ON if state == STATE_ON else STATE_OFF

        # Toggle all devices in this feeder
        for device_name, device_info in self._device_dict.items():
            if device_info[3] == feeder:
                self.device_variables[device_name].set(target_value)

    def _select_all(self) -> None:
        """Select all checkboxes."""
        set_all_checkboxes(self.device_variables, STATE_ON)
        set_all_checkboxes(self._substation_variables, STATE_ON)
        set_all_checkboxes(self._feeder_variables, STATE_ON)

    def _unselect_all(self) -> None:
        """Unselect all checkboxes."""
        set_all_checkboxes(self.device_variables, STATE_OFF)
        set_all_checkboxes(self._substation_variables, STATE_OFF)
        set_all_checkboxes(self._feeder_variables, STATE_OFF)

    def _on_ok(self, event: Optional[tk.Event] = None) -> None:
        """Handle OK button click."""
        if self._mode_var.get() == RADIO_VALUE_BATCH:
            self.batch_mode = True
        self.destroy()

    def _on_cancel(self, event: Optional[tk.Event] = None) -> None:
        """Handle Cancel button click."""
        self.cancelled = True
        self._unselect_all()
        self.destroy()


# =============================================================================
# Backward compatibility alias
# =============================================================================

# Keep the old class name available for any code that might reference it
DeviceSelection = DeviceSelectionDialog