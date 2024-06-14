""" UI stuff, uses tkinter for the GUI 5"""
import webbrowser
import threading
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as tkf
from tkinter import simpledialog, messagebox

from PIL import Image, ImageTk

from run import VERSION
from src import exceptions
from src.processing import storage
from src.logger import Logger


def queue_alert_message(references: dict, msg: str, *, warning=False):
    """ Add a alert message to the root thread queue
    :param references: (dict) references
    :param msg: (str) the message
    :param warning: (bool) if it is a warning
    :returns: (int) the time if it is a message
    """
    references["RootThread"].queue.append(
        {"cmd": "alert", "params": ["msg", msg], "kwargs": {"warning": warning}, "wait": True})


def queue_ask_question(references: dict, msg: str, title: str, callback):
    """ Add a popup message to the root thread queue
    :param references: (dict) references
    :param msg: (str) the message
    :param title: (str) the title
    :param callback: the callback function
    :returns: (int) the time if it is a message
    """
    references["RootThread"].queue.append(
        {"cmd": "alert", "params": ["popup", msg], "kwargs": {"ask": True, "title": title}, "wait": True,
         "callback": callback})


def queue_quit_message(references: dict, msg: str, title: str):
    """ Add a popup error to the root queue queue and then close the application (SystemTray.stopTray)
    :param references: references
    :param msg: (str) the message
    :param title: (str) the title
    :returns: (int) the time if it is a message
    """
    references["RootThread"].queue.append(
        {"cmd": "alert", "params": ["popup", msg], "kwargs": {"ask": False, "title": title}, "wait": False,
         "callback": references["SystemTray"].stop_tray})


class ScrollableFrame(tk.Frame):
    """ A frame with a scrollbar
    """

    def __init__(self, master, *args, **kwargs):
        """ Initialize
        :param master: the parent widget
        :param args:
        :param kwargs:
        """
        # Keep track
        self.initiated = False

        # That's the outer frame
        self.outer_frame = tk.Frame(master, *args, **kwargs)

        # Canvas
        payload = {}
        if "height" in kwargs:
            payload.update({"height": kwargs["height"]})

        if "width" in kwargs:
            payload.update({"width": kwargs["width"]})

        self.canvas = tk.Canvas(self.outer_frame, **payload)
        self.canvas.pack(side="left", fill="both", expand=True)

        # This obj is the inner frame, so that it can be passed directly on to an widget
        super().__init__(self.canvas)
        self.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self, anchor="nw")

        # Scrollbar
        self.scrollbar = ttk.Scrollbar(self.outer_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side="right", fill="y")

        # Configure canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        self.initiated = True

    def __getattribute__(self, item):
        """ Overriding attribute access so that for example .pack() gets called on the .outer_frame
        :param item: the name of the attribute
        :returns: the attribute
        """
        if object.__getattribute__(self, "initiated") and callable(object.__getattribute__(self, item)):
            return object.__getattribute__(self, "outer_frame").__getattribute__(item)

        return object.__getattribute__(self, item)

    def on_mousewheel(self, e):
        """ Event on mousewheel change
        :param e: event obj
        """
        self.canvas.yview_scroll(int(-1*(e.delta/120)), "units")


class RootThread(threading.Thread):
    """ The thread for the gui (tkinter)
    """

    def __init__(self, references: dict):
        """ Initialize
        :param references: references
        """
        super().__init__(name=self.__class__.__name__)
        self.references = references

        # Queue for executing methods inside the thread
        self.queue = []

        # The root window (tkinter.TK)
        self.root = None

        # Add thread to references
        self.references.update({"RootThread": self})

    def run(self) -> None:
        """ Run method of thread
        """
        try:
            Logger.log("Root Thread", add=True)

            # Initialize root and start the queue update
            self.root = Root(self.references)
            self.root.queue_update()

            # Start mainloop
            Logger.log("Root Gui", add=True)
            self.root.mainloop()
            Logger.log("Root Gui", add=False)

            Logger.log("Root Thread", add=False)

        # If something happens, log it
        except Exception as e:
            exceptions.handle_error(self.references)


class Root(tk.Tk):
    """ The root window of the application
    """

    def __init__(self, references):
        """ Initialize
        :param references: references
        """
        super().__init__()
        self.references = references

        self.storage = None

        # Setting up tk stuff
        self.title("FOV Changer")
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.resizable(False, False)
        self.geometry("800x440")
        self.tk.call('wm', 'iconphoto', self._w,
                     ImageTk.PhotoImage(Image.open(storage.find_file("res\\logo.ico", meipass=True))))

        # Used inside the queue_update()
        self.rendered = False

        # Ttk style
        self.style = ttk.Style()
        self.font = "Sans Serif"

        # Widgets whose reference are needed
        self.main_frame = None
        self.status_frame = None
        self.feature_frame = None
        self.feature_frame_placeholder = None
        self.start_button = None
        self.settings_frame = None
        self.log_frame = None
        self.log_text = None
        self.info_frame = None

        # TextVariables
        self.start_button_var = tk.StringVar()
        self.start_button_var.set("Start")
        self.setup_key_entry_var = tk.StringVar()

        # Images
        self.logo_image = None
        self.title_image = None

        # Message System
        self.notification_frame = None
        self.notification_label = None
        self.notification_message = tk.StringVar()

        # TopLevels
        self.feature_edit_manager = FeatureEditManager(self.references, self)

        # Cache some things
        self.cache = {
            "validate": "",  # On entry key validate
            "space": None  # Space between features
        }

        # As long there isn't any content, show waiting cursor
        self.config(cursor="wait")

        # Add to references
        self.references.update({"Root": self})

    def hide(self, *, not_exit_all=False):
        """ Hides the root (withdraws it)
        :param not_exit_all: if to not exit all
        """
        if not self.storage and "Storage" in self.references:
            self.storage = self.references["Storage"]

        if self.storage and self.storage.settings and self.storage.settings["exit_all"] and not not_exit_all or not self.references["SystemTray"].tray.visible:
            self.references["SystemTray"].stop_tray()

        else:
            self.withdraw()
            self.feature_edit_manager.hide_all()
            self.references["Storage"].update_file()

    def queue_update(self):
        """ Run every 500 ms a new task from the queue
            E.g. {"cmd": "alert", "params":["msg", "hey"], "kwargs":{}, wait=True, callback=print}}
        """
        try:
            task = self.references["RootThread"].queue.pop(0)

            # If it should wait to be rendered
            if "wait_for_render" in task and task["wait_for_render"] and not self.rendered:
                self.references["RootThread"].queue.append(task)

                t = 0

            else:
                # Attribute of thread
                if isinstance(task["cmd"], str):  # Please save this fix, i dont want to release another time .-.
                    t = getattr(self, task["cmd"])(*task["params"], **task["kwargs"])

                # Callable method
                elif callable(task["cmd"]):
                    t = task["cmd"](*task["params"], **task["kwargs"])

                else:
                    t = 0

                # If there is no wait
                if "wait" not in task or not task["wait"]:
                    t = 0

                # Check if there is a callback
                if "callback" in task:
                    task["callback"](t)

        except IndexError:
            # No tasks
            t = 0

        # Check return value
        if not isinstance(t, int):
            t = 2500

        # Update logs
        if Logger.queue:
            Logger.write_all()

        self.after(500 + t, self.queue_update)

    def create_widgets(self):
        """ Create all widgets
            https://coolors.co/3a606e-607b7d-828e82-aaae8e-e0e0e0
        """
        # Create style
        # Thanks to https://stackoverflow.com/a/23399786/11940809 and more
        # Remove Focus outline from Tab
        self.style.layout("Tab", [('Notebook.tab', {'sticky': 'nswe', 'children': [('Notebook.padding',
                                                                                    {'side': 'top', 'sticky': 'nswe',
                                                                                     'children': [('Notebook.label',
                                                                                                   {'side': 'top',
                                                                                                    'sticky': ''})]})]})])
        self.style.configure("Tab", padding=[51, 4], font=(self.font, 12))
        self.style.configure("TCheckbutton", font=(self.font, 13))
        self.style.configure("TEntry", padding=[10, 2, 10, 2])
        self.style.configure("TButton", font=(self.font, 12), padding=[30, 2, 30, 2])

        # Main frame
        self.main_frame = tk.Frame(self, bg="#E0E0E0")
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

        # The header frame is located above the content
        header_frame = tk.Frame(self.main_frame, bg="#3A606E")
        header_frame.grid(column=0, row=0, columnspan=4, sticky="WE")

        # Logo
        self.logo_image = ImageTk.PhotoImage(
            Image.open(storage.find_file("res\\logo-full.png", meipass=True)).resize((80, 80), Image.LANCZOS))
        tk.Label(header_frame, image=self.logo_image, borderwidth=0).pack(side="right", padx=3)

        # Title
        self.title_image = ImageTk.PhotoImage(
            Image.open(storage.find_file("res\\logo-title.png", meipass=True)).resize((280, 70), Image.LANCZOS))
        tk.Label(header_frame, image=self.title_image, borderwidth=0).pack(side="right", padx=6)

        # Notification
        self.notification_frame = tk.Frame(self.main_frame, bg="#E0E0E0", borderwidth=0)
        self.notification_label = tk.Label(self.notification_frame, bg="#E0E0E0", fg="#E0E0E0",
                                           textvariable=self.notification_message, font=(self.font, 14))

    def create_content(self):
        """ Sub create from createWidgets, initializes the content
            Will also create notebook
        """
        # Add storage
        self.storage = self.references["Storage"]

        # Control dashboard
        control_frame = tk.Frame(self.main_frame, bg="#E0E0E0")
        control_frame.grid(column=0, row=1, sticky="WENS")

        # Start button
        start_button_wrapper = tk.Frame(control_frame, width=200, highlightbackground="#3A606E", highlightthickness=2,
                                        cursor="hand2")
        self.start_button = tk.Button(start_button_wrapper, text="", font=(self.font, 11),
                                      takefocus=False, relief="flat", borderwidth=0, textvariable=self.start_button_var)
        start_button_cmd = lambda e: (self.references["ProcessingThread"].queue.append(
            {"cmd": "start_button_handle", "params": [e], "kwargs": {}}
        ))
        self.start_button.bind("<Button-1>", start_button_cmd)
        # self.start_button.bind("<Enter>", lambda e: e.widget.configure(bg="#3A606E", fg="#ffffff"))
        # self.start_button.bind("<Leave>", lambda e: e.widget.configure(bg="#ffffff", fg="#000000"))
        self.bind("<Return>", start_button_cmd)
        self.start_button.pack(fill="both")
        start_button_wrapper.grid(column=0, row=0, sticky="ew", padx=20, pady=25)

        # Status
        self.status_frame = tk.Frame(control_frame, width=128,
                                     bg="#f0f0f0", highlightbackground="#3A606E", highlightthickness=2)
        self.status_frame.grid(column=0, row=1, padx=20, pady=0, ipadx=10)
        self.status_frame.columnconfigure(1, weight=1)
        self.status_frame.rowconfigure(1, weight=1)

        self.render_status(self.references["Gateway"].status)

        # Separator
        tk.Frame(self.main_frame, bg="#3A606E").grid(column=2, row=1, sticky="WENS", ipadx=3)

        # Notebook
        self.create_notebook()

        # Return to default cursor
        self.config(cursor="arrow")

        # Update
        self.rendered = True

    def render_status(self, status: dict):
        """ Render a status
        :param status: the status
        """
        for child in self.status_frame.winfo_children():
            child.destroy()

        symbols = {True: "✔️", False: "❌", None: "⭕"}
        colors = {True: "#19b33d", False: "#eb4034", None: "#3A606E"}

        for x, (name, state) in enumerate(status.items()):
            s = tk.Label(self.status_frame, text=symbols[state], font=(self.font, 11),
                         fg=colors[state],
                         bg="#f0f0f0")
            s.grid(column=0, row=x, sticky="e", ipadx=10, ipady=10)

            if self.storage.features:
                if name in self.storage.features.data:
                    name = self.storage.features[name]["name"]

            t = tk.Label(self.status_frame, text=name, font=(self.font, 11), bg="#f0f0f0")
            t.grid(column=1, row=x, sticky="w", ipadx=0, ipady=10)

        self.update()

    def create_notebook(self):
        """ The notebook which contains settings and more is
            Gets execute in createContent
        """
        notebook = ttk.Notebook(self.main_frame, width=600, takefocus=False)
        notebook.grid(column=3, row=1, sticky="WENS", ipadx=0)

        # Create instances
        self.feature_frame = tk.Frame(notebook)
        self.settings_frame = tk.Frame(notebook)
        self.log_frame = tk.Frame(notebook)
        self.info_frame = tk.Frame(notebook)

        # Update to get height
        self.update()

        # Add them before to be then able to calculate the height
        notebook.add(self.feature_frame, text="Features")
        notebook.add(self.settings_frame, text="Settings")
        notebook.add(self.log_frame, text="Log")
        notebook.add(self.info_frame, text="Info")

        # Notebook Features
        # If there are features, render them
        if features := self.storage.features:
            self.create_tab_features(features)
            Logger.log("Rendered Features!")

        # or just make a placeholder
        else:
            self.feature_frame_placeholder = tk.Label(self.feature_frame,
                                                      text="Please start the FOV Changer once in order to"
                                                           " display the features!",
                                                      font=(self.font, 12), fg="#3A606E")
            self.feature_frame_placeholder.place(relx=.5, y=100, anchor="center")

        # Notebook Settings
        self.storage.settings.tk_vars = self.create_tab_settings()
        Logger.log("Rendered Settings!")

        # Notebook Log
        self.create_tab_log()

        # Notebook Info
        self.create_tab_info()

    def create_tab_features(self, features):
        """ Creates the Tab features + tk_vars
            Own Method to make it better to read
        :param features: (Features) the features object
        """
        # Remove placeholder
        if self.feature_frame_placeholder:
            self.feature_frame_placeholder.place_forget()

        # Calculate y padding
        space = round((self.feature_frame.winfo_height() - tkf.Font(font=(self.font, 13)).metrics(
            "linespace") * features.len) / (features.len + 2))
        self.cache.update({"features_space": space})

        # Vars for return
        payload = {}

        def render(feature: dict, feature_id: str, i: int, *, child=False) -> dict:
            """ Render function for better organisation
            :param feature: (dict) feature
            :param feature_id: the if of the feature
            :param i: (int) index
            :param child: if it is a child
            :returns: the tk vars
            """
            # Padding
            pad_y = space if i % 2 == 0 else 0
            extra_column = int(child)

            # Payload which gets merged into the main payload
            _payload = {"enabled": tk.IntVar(), "key": tk.StringVar(), "settings": {}}

            # Enable Button + Label
            enable_button = ttk.Checkbutton(self.feature_frame, text=f"   {feature['name']}",
                                            variable=_payload["enabled"], cursor="hand2")
            enable_button.bind("<Button-1>",
                               lambda e: self.on_feature_check_button(feature_id, _payload["enabled"].get()))
            enable_button.grid(column=extra_column, row=i, sticky="w", padx=30, pady=pad_y)
            _payload["enabled"].set(feature["enabled"] if feature["enabled"] is not None else False)

            # Entry for the key bind
            if not child and features.presets[feature_id]["g"].listener:
                entry = ttk.Entry(self.feature_frame, font=(self.font, 12), justify="center",
                                  textvariable=_payload["key"])
                entry.grid(column=1, row=i, sticky="ew", padx=10, pady=pad_y)
                _payload["key"].set(feature["key"])

                # Validation
                proc = entry.register(lambda p: self.on_feature_entry_validate(feature_id, p))
                entry.configure(validate="key", validatecommand=(proc, "%P"))

            else:
                # We dont need it
                entry = None
                _payload["key"] = None

            if feature["available"] and features.presets[feature_id]["g"].edit_button:
                # Edit Button
                edit_button_wrapper = tk.Frame(self.feature_frame, width=96, height=29, cursor="hand2")
                edit_button_wrapper.pack_propagate(0)
                edit_button = ttk.Button(edit_button_wrapper, text="Edit", takefocus=False)
                edit_button.bind("<Button-1>", lambda e: self.feature_edit_manager.open_feature(feature_id))
                edit_button.pack(fill="both")
                edit_button_wrapper.grid(column=2, row=i, sticky="w", padx=30, pady=pad_y)

                # Top level for edit button
                self.feature_edit_manager.add_feature(feature_id, feature, _payload)

            else:
                edit_button = None

            # If needed, disable
            if not feature["available"]:
                enable_button.state(["disabled"])
                if edit_button:
                    edit_button.state(["disabled"])

                _payload["enabled"].set(False)

                if entry:
                    entry.state(["disabled"])

            # Help url
            url = tk.Label(self.feature_frame, text="?", font=(self.font, 13), fg="#3A606E", cursor="hand2")
            url.grid(column=3, row=i, sticky="w", padx=10, pady=pad_y)
            url.bind("<Button-1>", lambda e: webbrowser.open(self.storage.get("features_help_url").format(feature_id), new=2))

            return _payload

        children = set()
        for value in features.data.values():
            if value["children"]:
                children.update(value["children"])

        # Iter through features
        i = 0
        done = set()
        for key, f in features.data.items():
            if key not in done and key not in children:
                payload.update({key: render(f, key, i)})
                done.add(key)

                i += 1

                # Create each child
                if f["children"]:
                    for child_key in f["children"]:
                        if child_key not in done:
                            payload.update({child_key: render(features.data[child_key], child_key, i, child=True)})
                            done.add(child_key)

                            i += 1

        del done

        self.storage.features.tk_vars = payload

    def create_tab_settings(self):
        """ Displays the settings
        """
        settings = self.storage.settings.data
        settings_url = self.storage.get("settings_help_url")

        settings_inner = ScrollableFrame(self.settings_frame, height=230)
        settings_inner.pack(expand=True, fill="x")

        # Calculate y padding
        length = len(settings) + 1
        space = round((self.feature_frame.winfo_height() - tkf.Font(font=(self.font, 13)).metrics(
            "linespace") * length) / (length + 2))

        def render(setting_name: str, setting_value: any, i: int):
            """ Render a setting
            :param setting_name: (str) name of setting
            :param setting_value: (any) value of setting
            :param i: (int) index
            """
            pad_y = space if i % 2 == 0 else 0

            tk_var = None

            # Text
            tk.Label(settings_inner, text=self.storage.settings.presets[setting_name]["n"], font=(self.font, 13)) \
                .grid(column=0, row=i, padx=30, pady=pad_y, sticky="e")

            # User input
            # Bool -> check button
            if isinstance(setting_value, bool):
                tk_var = tk.IntVar()

                setting_input = ttk.Checkbutton(settings_inner, takefocus=False, variable=tk_var)
                setting_input.grid(column=1, row=i, padx=10, pady=pad_y, sticky="w")

            # Function -> button
            elif callable(setting_value):
                tk_var = None

                setting_action = ttk.Button(settings_inner, text="Press me", takefocus=False,
                                            command=setting_value)
                setting_action.grid(column=1, row=i, padx=10, pady=pad_y, sticky="ew")

            # Else
            else:
                tk_var = tk.StringVar()

                setting_input = ttk.Entry(settings_inner, font=(self.font, 12), justify="left",
                                          textvariable=tk_var,
                                          takefocus=False)
                setting_input.grid(column=1, row=i, padx=10, pady=pad_y, sticky="w", ipadx=40)

            # Help url
            url = tk.Label(settings_inner, text="?", font=(self.font, 13), fg="#3A606E", cursor="hand2")
            url.grid(column=3, row=i, sticky="e", padx=50, pady=space if i % 2 == 0 else 0)
            url.bind("<Button-1>", lambda e: webbrowser.open(settings_url.format(setting_name), new=2))

            # Has a user input?
            if tk_var:
                tk_var.set(setting_value)
                return tk_var

            return None

        tk_vars = {}

        i = 0
        for name, value in settings.items():
            tk_vars.update({name: render(name, value, i)})
            i += 1

        # tk.Frame(self.settings_frame, bg="red", height=10).pack(expand=True, fill="x")

        # Create save button + help button
        save_button = ttk.Button(self.settings_frame, text="Save", takefocus=False,
                                 command=self.on_settings_save_button)
        save_button.pack(pady=30)

        return tk_vars

    def create_tab_log(self):
        """ Creates the tab log, show logger messages
            Replacement for normal console
        """
        # "Border" for log messages
        inner_frame = tk.Frame(self.log_frame)
        inner_frame.pack(fill="both", padx=0, pady=20)

        # Scrollbar for text
        scrollbar = ttk.Scrollbar(inner_frame)
        scrollbar.pack(side="right", fill="y")

        # Log text
        self.log_text = tk.Text(inner_frame, height=400, yscrollcommand=scrollbar.set, relief="flat", borderwidth=12,
                                font=("Consolas", 13), bg="#121212", fg="#ffffff", state="disabled")
        self.log_text.pack(side="top", fill="y")

        scrollbar.config(command=self.log_text.yview)

    def create_tab_info(self):
        """ Provides information about the current version, author and more
        """
        tk.Label(self.info_frame, text="Made by XroixHD", font=(self.font, 13)) \
            .pack(padx=50, pady=30)

        ttk.Button(self.info_frame, text="Github", takefocus=False,
                   command=lambda: webbrowser.open("https://www.github.com/XroixHD/MCBE-Win10-FOV-Changer", new=2)) \
            .pack(padx=50, pady=10)

        ttk.Button(self.info_frame, text="Docs", takefocus=False,
                   command=lambda: webbrowser.open("https://fov.xroix.me/docs", new=2)) \
            .pack(padx=50, pady=0)

        ttk.Button(self.info_frame, text="Discord", takefocus=False,
                   command=lambda: webbrowser.open("https://discord.gg/H3hex27", new=2)) \
            .pack(padx=50, pady=10)

        tk.Label(self.info_frame, text=f"v{VERSION}", font=("Consolas", 13)) \
            .pack(padx=50, pady=10)

    def on_feature_entry_validate(self, feature_id: str, p: str):
        """ On validation of a feature key entry
        :param feature_id: (str) if of the feature
        :param p: (str) %P => content
        """
        # Cache
        if (p != "" and p == self.cache["validate"]) or len(p) > 1:
            self.bell()
            return False

        self.cache["validate"] = p

        # Change feature + prepare storage for update queue + register keys in listener new
        self.storage.features[feature_id]["key"] = p[0] if p else ""
        with self.storage.edited_lock:
            self.storage.edited = True

        with self.storage.listener_keys_edited_lock:
            self.storage.listener_keys_edited = True

        return True

    def on_feature_check_button(self, feature_id: str, state):
        """ On click of a feature check button
        :param feature_id: (str)  if of the feature
        :param state: state of the button
        """
        feature_value = self.storage.features[feature_id]

        if feature_value["available"]:

            # Reverse it because it's needed + save it
            feature_value["enabled"] = not state

            with self.storage.edited_lock:
                self.storage.edited = True

            # Update status
            if feature_id in self.references["Gateway"].status:
                self.references["ProcessingThread"].queue.append(
                    {"cmd": self.references["Gateway"].status_check, "params": [], "kwargs": {}})

    def on_settings_save_button(self):
        """ Save settings
        """
        if self.storage.settings.tk_vars:
            settings = self.storage.settings.data

            for name, value in self.storage.settings.tk_vars.items():
                try:
                    # Try to cast
                    value = type(settings[name])(value.get())

                    # Set new value
                    settings[name] = value

                except ValueError:
                    Logger.log(msg := f"Invalid value for {' '.join(x[0].upper() + x[1:] for x in name.split('_'))}")
                    queue_alert_message(self.references, msg, warning=True)
                    return

            Logger.log("Saved new settings!")
            queue_alert_message(self.references, "Saved new settings!")

        self.storage.update_file()

    def alert(self, mode: str, msg: str, *, warning=False, ask=False, title="Untitled") -> any:
        """ Alert a message or a popup
        :param mode: (str) either 'popup' or 'msg', falls back to msg
        :param msg: (str) the message
        :param warning: (bool) if it is a warning
        :param ask: (bool) if a popup should ask
        :param title: (str) the title of a popup
        :returns: (int) the time if it is a message
        """
        # Pop ups
        if mode.lower() == "popup":
            if ask:
                return simpledialog.askstring(title=title, prompt=msg)

            else:
                return messagebox.showerror(title=title, message=msg)

        # A message, display at footer
        else:
            # Change color
            if warning:
                self.notification_frame["bg"] = "#eb4034"
                self.notification_label["bg"] = "#eb4034"

            else:
                self.notification_frame["bg"] = "#3A606E"
                self.notification_label["bg"] = "#3A606E"

            # Set message
            self.notification_message.set(msg)

            # Pack and grid it
            self.notification_frame.grid(column=0, row=2, columnspan=4, sticky="WE", padx=0, pady=0)
            self.notification_label.pack(padx=5, pady=5)
            self.update()

            # And the invoke, time is calculate with 'round(len(msg) / 5 / 180 * 60 * 4) * 1000'
            # However, to speed up, it used the rough 'len(msg) * 266'
            self.after((n := len(msg) * 266),
                       lambda: (self.notification_label.pack_forget(), self.notification_frame.grid_forget()))

            return n


class FeatureEditManager:
    """ Manages the feature edit top levels
    """

    def __init__(self, references: dict, root: tk.Tk):
        """ Initialize
        :param references: the references
        :param root: the root
        """
        # Settings
        self.references = references
        self.root = root
        self.storage = self.references["Storage"]

        # TopLevels
        self.top_levels = {}

        # Fix bug
        self.open = False

    def position(self, feature_id):
        """ Position a top level
        :param feature_id: the id of the feature
        """
        self.top_levels[feature_id].geometry(f"300x150+{self.root.winfo_x()}+{self.root.winfo_y()}")

    def add_feature(self, feature_id: str, feature: dict, payload: dict):
        """ Add features
        :param feature_id: (str) the if of the feature
        :param feature: (dict) the feature
        :param payload: (dict) the payload
        """
        # Create Top Level
        top = tk.Toplevel(self.root)
        top.withdraw()
        top.title(feature["name"])
        top.tk.call('wm', 'iconphoto', top._w,
                    ImageTk.PhotoImage(Image.open(storage.find_file("res\\logo.ico", meipass=True))))
        top.geometry(f"300x150+{self.root.winfo_x()}+{self.root.winfo_y()}")
        top.resizable(False, False)
        top.protocol("WM_DELETE_WINDOW", lambda: (self.hide(feature_id)))
        # top.bind("<Return>", lambda e: self.save(feature_id))

        # Load content  based on feature group
        self.storage.features.presets[feature_id]["g"].create_edit_button_widgets(manager=self, top=top, feature_id=feature_id, feature=feature, payload=payload)

        # Add it
        self.top_levels.update({feature_id: top})

    def open_feature(self, feature_id: str):
        """ Open a specific feature top level
        :param feature_id: the if of the feature
        """
        if not self.open and self.storage.features[feature_id]["available"]:
            self.top_levels[feature_id].deiconify()
            self.top_levels[feature_id].grab_set()
            self.position(feature_id)

            self.open = True

    def save(self, feature_id: str):
        """ Click event for save button
        :param feature_id: the id of the feature
        """
        if self.open:
            # Hide window
            self.top_levels[feature_id].withdraw()
            self.top_levels[feature_id].grab_release()

            # Get some values to clean up code
            feature = self.storage.features[feature_id]
            tk_var = self.storage.features.tk_vars[feature_id]["settings"]
            presets = self.storage.features.presets[feature_id]

            settings = {x: y.get() for x, y in tk_var.items()}

            # Save new values into the real settings field and check type
            # Also translate the values if needed
            if self.storage.features.check_settings(self.storage.features, feature_id, feature, override=settings):
                feature["settings"] = settings
                self.references["Storage"].update_file()

                Logger.log(f"Saved new values! [{settings}]")
                # queue_alert_message(self.references, "Saved new values!")

            # Reset from real saved value
            else:
                Logger.log(f"Invalid value entered! [{settings}]")
                queue_alert_message(self.references, "Invalid value entered!", warning=True)
                for var_name, var_obj in tk_var.items():
                    var_obj.set((str(temp if (temp := feature["settings"][var_name]) is not None else "")))

            self.open = False

    def hide(self, feature_id: str):
        """ Hide a top level, like save() but without saving stuff
        :param feature_id: the id of the feature
        """
        if self.open:
            # Hide window
            self.top_levels[feature_id].withdraw()
            self.top_levels[feature_id].grab_release()

            self.open = False

    def hide_all(self):
        """ Hides / Withdraws all top levels
        """
        for top_level_obj in self.top_levels.values():
            top_level_obj.withdraw()
            top_level_obj.grab_release()
