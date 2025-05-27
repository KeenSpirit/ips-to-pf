import tkinter as tk
from tkinter import *  # noqa [F403]
from tkinter import ttk


def user_selection(app, device_dict):
    """Present the user with a structure to select the relays that they
    would like to study. Return the list of selected devices."""
    selection = DeviceSelection(device_dict)
    if selection.cancel:
        return None
    if selection.batch:
        return "Batch"
    # Get a list of devices that have been selected
    selected_devices = []
    for element in selection.device_ordered_list:
        state = selection.variables_dict[element].get()
        if state == "On":
            selected_devices += [element]
    return selected_devices


class DeviceSelection(Tk):
    """This class is used to record the protection devices that the user wants
    to study"""

    def __init__(self, device_dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define class attributes
        self.device_dict = device_dict
        self.variables_dict = {}
        self.device_ordered_list = []
        self.cancel = False
        self.selection = None
        self.batch = False
        # Build up the widget
        self.title("IPS Device Import")
        self.create_widgets()
        self.resizable(False, False)
        # Keep window on top
        self.wm_attributes("-topmost", 1)
        # Place the widget in the middle of the screen
        x = (self.winfo_screenwidth() - self.winfo_reqwidth()) / 2
        y = ((self.winfo_screenheight() - self.winfo_reqheight()) / 2) - 250
        self.geometry("+%d+%d" % (x, y))
        self.focus_force()
        self.mainloop()

    def create_widgets(self):
        """This function will build the user interface objects"""

        # Radio button frame at the top
        self.radio_frame = ttk.Frame(self)
        self.radio_frame.pack(pady=10)

        # Radio button variable
        self.selection_var = StringVar(value="selection1")

        # Radio buttons
        self.radio1 = ttk.Radiobutton(
            self.radio_frame,
            text="Update study case with all protection devices from IPS",
            variable=self.selection_var,
            value="selection1",
            command=self.on_radio_change,
        )
        self.radio1.pack(anchor=W)

        self.radio2 = ttk.Radiobutton(
            self.radio_frame,
            text="Update only the following selected devices:",
            variable=self.selection_var,
            value="selection2",
            command=self.on_radio_change,
        )
        self.radio2.pack(anchor=W)

        # self.style = ttk.Style()
        # self.style.configure("TRadiobutton", font=('Helvetica', 12))

        # Frame for Select All and Unselect All buttons
        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(pady=5)

        self.select_all_btn = ttk.Button(
            self.button_frame,
            text="Select All",
            command=self.select_all,
            state=DISABLED
        )
        self.select_all_btn.grid(column=0, row=0, padx=5)

        self.unselect_all_btn = ttk.Button(
            self.button_frame,
            text="Unselect All",
            command=self.unselect_all,
            state=DISABLED
        )
        self.unselect_all_btn.grid(column=1, row=0, padx=5)

        # Configure the frame to house the check boxes with vertical scroll bar
        self.frame = VerticalScrolledFrame(self)
        self.list_build()
        self.frame.pack(fill=BOTH, expand=True, pady=5)

        # Set initial state of scrollable content to disabled
        self.set_checkboxes_state(DISABLED)

        # Configure a frame that houses action buttons at the bottom
        self.action_frame = ttk.Frame(self)
        self.action_frame.pack(pady=10)

        ttk.Button(self.action_frame, text="OK", command=self.ok).grid(
            column=0, row=0, padx=5
        )
        ttk.Button(self.action_frame, text="Cancel", command=self.cancel_script).grid(
            column=1, row=0, padx=5
        )

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel_script)

    def on_radio_change(self):
        """Handle radio button selection changes"""
        if self.selection_var.get() == "selection1":
            # Disable checkboxes and buttons
            self.select_all_btn.config(state=DISABLED)
            self.unselect_all_btn.config(state=DISABLED)
            self.set_checkboxes_state(DISABLED)
        else:
            # Enable checkboxes and buttons
            self.select_all_btn.config(state=NORMAL)
            self.unselect_all_btn.config(state=NORMAL)
            self.set_checkboxes_state(NORMAL)

    def set_checkboxes_state(self, state):
        """Set the state of all checkboxes"""
        for widget in self.frame.interior.winfo_children():
            if isinstance(widget, ttk.Checkbutton):
                widget.config(state=state)

    def list_build(self):
        """This function will add text with no indent for the substation, one indent for feeder
        and then a check box for all active devices in that feeder."""
        self.sub_dict = {}
        self.feeder_dict = {}
        self.var = {}
        list_of_devices = [device for device in self.device_dict]
        for device in list_of_devices:
            # Check to see if there is an entrance for the substation
            sub = self.device_dict[device][4]
            if sub not in self.sub_dict:
                self.var[sub] = StringVar()
                self.option_check = ttk.Checkbutton(
                    self.frame.interior,
                    text="{}".format(sub),
                    variable=self.var[sub],
                    onvalue="On",
                    offvalue="Off",
                    command=lambda key=sub: self.select_feeders(key),
                ).pack(anchor=W, padx=0)
                self.sub_dict[sub] = self.var[sub]
                for device in list_of_devices:
                    # Record all the devices that belong to this substation
                    if sub != self.device_dict[device][4]:
                        continue
                    feeder = self.device_dict[device][3]
                    if feeder not in self.feeder_dict:
                        self.var[feeder] = StringVar()
                        self.option_check = ttk.Checkbutton(
                            self.frame.interior,
                            text="{}".format(feeder),
                            variable=self.var[feeder],
                            onvalue="On",
                            offvalue="Off",
                            command=lambda key=feeder: self.select_devices(key),
                        ).pack(anchor=W, padx=30)
                        self.feeder_dict[feeder] = self.var[feeder]
                        for device in list_of_devices:
                            # Record all the devices that belong to this feeder
                            if feeder != self.device_dict[device][3]:
                                continue
                            if device not in self.variables_dict:
                                self.check = StringVar()
                                self.option_check = ttk.Checkbutton(
                                    self.frame.interior,
                                    text="{}".format(device),
                                    variable=self.check,
                                    onvalue="On",
                                    offvalue="Off",
                                ).pack(anchor=W, padx=90)
                                # Create a dictionary and an ordered list of
                                # tree structure for use later in the script.
                                self.variables_dict[device] = self.check
                                self.device_ordered_list += [device]

    def ok(self, event=None):
        """Modified OK button functionality"""
        if self.selection_var.get() == "selection1":
            # Return "Batch" for Selection 1
            self.selection = "Batch"
            self.batch = True
        else:
            # Return dictionary of selected devices grouped by feeder for Selection 2
            selected_devices = {}
            for device_name, var in self.variables_dict.items():
                if var.get() == "On":
                    feeder_name = self.device_dict[device_name][3]
                    if feeder_name not in selected_devices:
                        selected_devices[feeder_name] = []
                    selected_devices[feeder_name].append(device_name)
            self.selection = selected_devices
        self.destroy()

    def cancel_script(self, event=None):
        self.cancel = True
        self.unselect_all()
        self.destroy()

    def select_all(self):
        """This function is turn all checkboxes on"""
        for name in self.variables_dict:
            self.variables_dict[name].set("On")
        for name in self.sub_dict:
            self.sub_dict[name].set("On")
        for name in self.feeder_dict:
            self.feeder_dict[name].set("On")

    def unselect_all(self):
        """This function is turn all checkboxes off"""
        for name in self.variables_dict:
            self.variables_dict[name].set("Off")
        for name in self.sub_dict:
            self.sub_dict[name].set("Off")
        for name in self.feeder_dict:
            self.feeder_dict[name].set("Off")

    def select_feeders(self, key):
        """If the sub is ON then all of the feeders should be on as well"""
        state = self.var[key].get()
        if state == "On":
            for device in self.device_dict:
                if key == self.device_dict[device][4]:
                    self.variables_dict[device].set("On")
                    self.feeder_dict[self.device_dict[device][3]].set("On")
        else:
            for device in self.device_dict:
                if key == self.device_dict[device][4]:
                    self.variables_dict[device].set("Off")
                    self.feeder_dict[self.device_dict[device][3]].set("Off")

    def select_devices(self, key):
        """If the user selects a feeder all the devices below it will turned
        on. If the user unselects a feeder all device turns off"""
        state = self.var[key].get()
        if state == "On":
            for device in self.device_dict:
                if key == self.device_dict[device][3]:
                    self.variables_dict[device].set("On")
        else:
            for device in self.device_dict:
                if key == self.device_dict[device][3]:
                    self.variables_dict[device].set("Off")


class VerticalScrolledFrame(ttk.Frame):
    """
    * Use the 'interior' attribute to place widgets inside the scrollable frame
    * Construct and pack/place/grid normally
    * This frame only allows vertical scrolling
    """

    def __init__(self, parent, *args, **kw):
        Frame.__init__(self, parent, *args, **kw)
        # create a canvas object and a vertical scrollbar for scrolling it
        vscrollbar = ttk.Scrollbar(self, orient=VERTICAL)
        vscrollbar.pack(fill=Y, side=RIGHT, expand=FALSE)
        canvas = Canvas(
            self, bd=0, highlightthickness=0, yscrollcommand=vscrollbar.set, height=400
        )
        canvas.pack(side=LEFT, fill=BOTH, expand=TRUE)
        vscrollbar.config(command=canvas.yview)
        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)
        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = ttk.Frame(canvas)
        interior_id = canvas.create_window(0, 0, window=interior, anchor=NW)

        def _configure_interior(event):
            # update the scrollbars to match the size of the inner frame
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                canvas.config(width=interior.winfo_reqwidth())

        interior.bind("<Configure>", _configure_interior)

        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the inner frame's width to fill the canvas
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())
                canvas.bind("<Configure>", _configure_canvas)
                return