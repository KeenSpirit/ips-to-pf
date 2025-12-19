"""
UI constants for the IPS to PowerFactory application.

This module centralizes UI-related constants including:
- Window titles and labels
- Padding and spacing values
- Button text
- State values

Centralizing these values makes it easy to maintain consistent
styling and enables localization if needed in the future.
"""

# =============================================================================
# Window Configuration
# =============================================================================

# Window title
WINDOW_TITLE = "IPS Device Import"

# Window positioning offset from center (pixels)
WINDOW_Y_OFFSET = -250

# Keep window on top
WINDOW_TOPMOST = True


# =============================================================================
# Radio Button Options
# =============================================================================

# Radio button labels
RADIO_BATCH_LABEL = "Update study case with all protection devices from IPS"
RADIO_SELECT_LABEL = "Update only the following selected devices:"

# Radio button values
RADIO_VALUE_BATCH = "selection1"
RADIO_VALUE_SELECT = "selection2"


# =============================================================================
# Button Text
# =============================================================================

BUTTON_OK = "OK"
BUTTON_CANCEL = "Cancel"
BUTTON_SELECT_ALL = "Select All"
BUTTON_UNSELECT_ALL = "Unselect All"


# =============================================================================
# State Values
# =============================================================================

# Checkbox states
STATE_ON = "On"
STATE_OFF = "Off"

# Return values
RETURN_BATCH = "Batch"


# =============================================================================
# Layout Constants
# =============================================================================

# Padding values (pixels)
PADDING_FRAME = 10
PADDING_BUTTON = 5
PADDING_CHECKBOX_SUB = 0       # Substation level indent
PADDING_CHECKBOX_FEEDER = 30   # Feeder level indent
PADDING_CHECKBOX_DEVICE = 90   # Device level indent

# Scrollable frame height
SCROLL_FRAME_HEIGHT = 400


# =============================================================================
# Keyboard Bindings
# =============================================================================

KEY_ENTER = "<Return>"
KEY_ESCAPE = "<Escape>"