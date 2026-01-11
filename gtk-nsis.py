#!/usr/bin/env python3
import sys

# Read flags BEFORE GTK eats them
STEVE_BALLMER_MODE = "--steve-ballmer" in sys.argv
BALLMER_WORD = "developers"

# Remove custom flags so GTK doesn't choke on them
sys.argv = [arg for arg in sys.argv if arg != "--steve-ballmer"]

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib

import subprocess
import threading
import shutil
import random
import re

# ---------------------- helpers: ballmerize & package manager ----------------------

def ballmerize(text: str, skip=False) -> str:
    if skip or not STEVE_BALLMER_MODE or not text:
        return text
    return re.sub(r"\b\w+\b", BALLMER_WORD, text)


def detect_package_manager():
    if shutil.which("apt"):
        return "apt"
    if shutil.which("dnf"):
        return "dnf"
    if shutil.which("pacman"):
        return "pacman"
    return None


def get_metadata_apt(pkg):
    try:
        out = subprocess.check_output(
            ["apt-cache", "show", pkg],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None

    info = {"depends": []}
    for line in out.splitlines():
        if line.startswith("Package:"):
            info["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Version:"):
            info["version"] = line.split(":", 1)[1].strip()
        elif line.startswith("Description:"):
            info["description"] = line.split(":", 1)[1].strip()
        elif line.startswith("Depends:"):
            deps = line.split(":", 1)[1].strip()
            info["depends"] = [d.strip().split(" ")[0] for d in deps.split(",")]
        elif line.startswith("Homepage:"):
            info["homepage"] = line.split(":", 1)[1].strip()
    return info


def get_metadata_dnf(pkg):
    try:
        out = subprocess.check_output(
            ["dnf", "info", pkg],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None

    info = {"depends": []}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Name"):
            info["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Version"):
            info["version"] = line.split(":", 1)[1].strip()
        elif line.startswith("Summary"):
            info["description"] = line.split(":", 1)[1].strip()
        elif line.startswith("URL"):
            info["homepage"] = line.split(":", 1)[1].strip()
    return info


def get_metadata_pacman(pkg):
    try:
        out = subprocess.check_output(
            ["pacman", "-Si", pkg],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None

    info = {"depends": []}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Name"):
            info["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Version"):
            info["version"] = line.split(":", 1)[1].strip()
        elif line.startswith("Description"):
            info["description"] = line.split(":", 1)[1].strip()
        elif line.startswith("URL"):
            info["homepage"] = line.split(":", 1)[1].strip()
        elif line.startswith("Depends On"):
            deps = line.split(":", 1)[1].strip()
            if deps != "None":
                info["depends"] = [d.strip().split(" ")[0] for d in deps.split("  ")]
    return info


def get_package_metadata(manager, pkg):
    if manager == "apt":
        return get_metadata_apt(pkg)
    if manager == "dnf":
        return get_metadata_dnf(pkg)
    if manager == "pacman":
        return get_metadata_pacman(pkg)
    return None


def is_installed(manager, pkg):
    try:
        if manager == "apt":
            subprocess.check_output(["dpkg", "-s", pkg], stderr=subprocess.STDOUT)
            return True
        if manager == "dnf":
            out = subprocess.check_output(
                ["dnf", "list", "installed", pkg],
                stderr=subprocess.STDOUT,
                text=True,
            )
            return pkg in out
        if manager == "pacman":
            subprocess.check_output(["pacman", "-Qi", pkg], stderr=subprocess.STDOUT)
            return True
    except subprocess.CalledProcessError:
        return False
    return False


def friendly_name_from_pkg(pkg):
    return " ".join(word.capitalize() for word in pkg.replace("-", " ").split())


# ---------------------- special triggers ----------------------


def is_windows_malware_phrase(text: str) -> bool:
    return text.strip().lower() == "i want to install windows malware"


def is_windows_promotional(text: str) -> bool:
    t = text.strip().lower()
    return "windows promotional" in t or "microsoft promotional" in t


def is_sandisk_assistant(text: str) -> bool:
    return text.strip().lower() == "sandisk assistant"


def is_wd_assistant(text: str) -> bool:
    return text.strip().lower() == "wd assistant"


def is_seagate_dashboard(text: str) -> bool:
    return text.strip().lower() == "seagate dashboard"


def is_rgb_mouse_installer(text: str) -> bool:
    return text.strip().lower() == "rgb gaming mouse driver installer"


def is_printer_setup_wizard(text: str) -> bool:
    return text.strip().lower() == "printer setup wizard"


def random_windows_promo():
    promos = [
        (
            "Microsoft 365 – The Future of Productivity",
            "Get the full Microsoft 365 experience with AI‑powered features, deep integration, and recurring billing.\n"
            "On Linux? Not really. But imagine the upsell popups anyway.",
        ),
        (
            "OneDrive – Your Files, Our Cloud",
            "Never lose a file again… unless sync breaks.\n"
            "On Linux, you’ll mostly get the vibes, not the native client.",
        ),
        (
            "Xbox Game Pass for PC – So Many Games",
            "Hundreds of games, one subscription, and a lot of green branding.\n"
            "On Linux, you might want to look at Proton and friends instead.",
        ),
        (
            "Copilot – AI Everywhere",
            "Get suggestions, completions, and the occasional ‘are you sure?’ dialog.\n"
            "On Linux, you already have your own vibe‑coded assistant.",
        ),
        (
            "NTFS – Clearly Superior to EXT4 (Allegedly)",
            "Enjoy journaling, permissions, and the eternal debate about which filesystem is ‘better’.\n"
            "On Linux, EXT4 quietly keeps doing its job while NTFS shouts from the sidelines.",
        ),
        (
            "Windows 11 – Latest Update Required",
            "We’ve prepared a few updates. And by a few, we mean many.\n"
            "On Linux, you get to choose when to update. Mostly.",
        ),
    ]
    return random.choice(promos)


# ---------------------- selection dialog ----------------------


class PackageSelectionDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Select Package", transient_for=parent, modal=True)
        self.set_default_size(420, -1)
        self.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        self.set_child(box)

        label = Gtk.Label(label="Enter the package/software you want to manage:")
        label.set_xalign(0.0)
        box.append(label)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("e.g. vlc, firefox, htop")
        box.append(self.entry)

        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.append(mode_box)

        mode_label = Gtk.Label(label="Action:")
        mode_label.set_xalign(0.0)
        mode_box.append(mode_label)

        self.mode_model = Gtk.StringList.new(["Install", "Uninstall"])
        self.mode_combo = Gtk.DropDown(model=self.mode_model)
        self.mode_combo.set_selected(0)
        mode_box.append(self.mode_combo)

        self.doc_revealer = Gtk.Revealer()
        self.doc_revealer.set_reveal_child(False)

        doc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        doc_box.set_margin_top(6)
        doc_box.set_margin_bottom(6)
        doc_box.set_margin_start(6)
        doc_box.set_margin_end(6)

        doc_title = Gtk.Label()
        doc_title.set_markup("<b>Special Features &amp; Joke Installers</b>")
        doc_title.set_xalign(0.0)
        doc_box.append(doc_title)

        docs = [
            "• Typing: “I want to install Windows malware” → Opens Windows Malware Joke Installer",
            "• Typing: “Sandisk Assistant” → Opens Sandisk Joke Installer",
            "• Typing: “WD Assistant” → Opens WD Assistant Joke Installer",
            "• Typing: “Seagate Dashboard” → Opens Seagate Dashboard Joke Installer",
            "• Typing: “RGB Gaming Mouse Driver Installer” → Opens RGB Mouse Joke Installer",
            "• Typing: “Printer Setup Wizard” → Opens Printer Setup Wizard (crashes realistically)",
            "• Typing: “Windows Promotional” or “Microsoft Promotional” → Shows random Microsoft promo popup",
            "• Running with --steve-ballmer → Nearly all words become “developers”, application unusable",
        ]

        for line in docs:
            lbl = Gtk.Label(label=line)
            lbl.set_xalign(0.0)
            lbl.set_wrap(True)
            doc_box.append(lbl)

        self.doc_revealer.set_child(doc_box)
        box.append(self.doc_revealer)

        self.doc_button = Gtk.Button(label="Show documentation")
        self.doc_button.connect("clicked", self.toggle_docs)
        box.append(self.doc_button)

        alert = Gtk.Label(
            label="⚠️ This installer was vibe‑coded. It may contain bugs."
        )
        alert.set_xalign(0.0)
        alert.add_css_class("warning")
        box.append(alert)

        button_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )
        box.append(button_row)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.set_icon_name("window-close-symbolic")
        cancel_btn.connect(
            "clicked", lambda *_: self.emit("response", Gtk.ResponseType.CANCEL)
        )
        button_row.append(cancel_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        button_row.append(spacer)

        ok_btn = Gtk.Button(label="OK")
        ok_btn.set_icon_name("emblem-ok-symbolic")
        ok_btn.connect(
            "clicked", lambda *_: self.emit("response", Gtk.ResponseType.OK)
        )
        ok_btn.set_receives_default(True)
        button_row.append(ok_btn)

        self.set_default_widget(ok_btn)

        self.entry.connect(
            "activate", lambda *_: self.emit("response", Gtk.ResponseType.OK)
        )

    def toggle_docs(self, button):
        current = self.doc_revealer.get_reveal_child()
        self.doc_revealer.set_reveal_child(not current)
        button.set_label("Hide documentation" if not current else "Show documentation")

    def get_package_name(self):
        return self.entry.get_text().strip()

    def get_mode(self):
        idx = self.mode_combo.get_selected()
        return "uninstall" if idx == 1 else "install"


# ---------------------- Sandisk joke installer ----------------------


class SandiskJokeInstallerWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.connect("close-request", lambda *a: self.app.quit())
        self.app = app
        self.set_title("Sandisk Assistant Setup (Fake)")
        self.set_default_size(600, -1)
        self.set_resizable(False)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Sandisk Assistant Setup (Fake)"))
        self.set_titlebar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(content)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sidebar.set_margin_top(16)
        sidebar.set_margin_bottom(16)
        sidebar.set_margin_start(16)
        sidebar.set_margin_end(0)
        sidebar.add_css_class("sidebar")
        content.append(sidebar)

        icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
        icon.set_pixel_size(48)
        sidebar.append(icon)

        steps_label = Gtk.Label(label="Steps")
        steps_label.set_xalign(0.0)
        steps_label.add_css_class("wizard-title")
        sidebar.append(steps_label)

        self.steps_list = Gtk.ListBox()
        self.steps_list.set_selection_mode(Gtk.SelectionMode.NONE)
        sidebar.append(self.steps_list)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.set_margin_top(16)
        self.stack.set_margin_bottom(16)
        self.stack.set_margin_start(0)
        self.stack.set_margin_end(16)
        content.append(self.stack)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(separator)

        button_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_panel.set_margin_top(6)
        button_panel.set_margin_bottom(6)
        button_panel.set_margin_start(12)
        button_panel.set_margin_end(12)
        root.append(button_panel)

        spacer = Gtk.Box()
        button_panel.append(spacer)

        self.back_button = Gtk.Button(label="Back")
        self.next_button = Gtk.Button(label="Next")
        self.cancel_button = Gtk.Button(label="Cancel")

        button_panel.append(self.back_button)
        button_panel.append(self.next_button)
        button_panel.append(self.cancel_button)

        self.back_button.connect("clicked", self.on_back_clicked)
        self.next_button.connect("clicked", self.on_next_clicked)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)

        self.page_ids = []
        self.page_titles = []
        self.current_index = 0

        self.build_pages()
        self.build_sidebar_steps()
        self.show_page(0)
        self.apply_css()

    def apply_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            .wizard-title {
                font-size: 18px;
                font-weight: bold;
            }
            .wizard-body {
                font-size: 14px;
            }
            button {
                padding: 8px 18px;
                font-size: 14px;
            }
            .sidebar {
                border-right: 1px solid @borders;
                padding-right: 12px;
            }
            .step-row.selected {
                background-color: @accent_bg_color;
                color: @accent_fg_color;
            }
        """
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_pages(self):
        self.build_welcome_page()
        self.build_install_page()

    def build_sidebar_steps(self):
        self.steps_list.remove_all()
        for idx, title in enumerate(self.page_titles):
            row = Gtk.ListBoxRow()
            row.add_css_class("step-row")
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            box.set_margin_start(4)
            box.set_margin_end(4)

            icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
            icon.set_pixel_size(16)
            box.append(icon)

            label = Gtk.Label(label=title)
            label.set_xalign(0.0)
            box.append(label)

            row.set_child(box)
            self.steps_list.append(row)

        self.update_sidebar_selection()

    def update_sidebar_selection(self):
        for i, row in enumerate(self.steps_list):
            if i == self.current_index:
                row.add_css_class("selected")
            else:
                row.remove_css_class("selected")

    def build_welcome_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup(
            "<span size='large' weight='bold'>Welcome to the Sandisk Assistant Setup (Fake)</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")

        desc = Gtk.Label(
            label=ballmerize(
                "You don’t need any Sandisk software to store data on your external drive.\n"
                "Linux already handles that for you."
            )
        )
        desc.set_wrap(True)
        desc.set_xalign(0.0)
        desc.add_css_class("wizard-body")

        info = Gtk.Label(
            label=ballmerize(
                "This is a joke installer. Nothing will be installed.\n"
                "Click Next to continue."
            )
        )
        info.set_wrap(True)
        info.set_xalign(0.0)
        info.add_css_class("wizard-body")

        box.append(title)
        box.append(desc)
        box.append(info)

        self.stack.add_titled(box, "welcome", "Welcome")
        self.page_ids.append("welcome")
        self.page_titles.append("Welcome")

    def build_install_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup(
            "<span size='large' weight='bold'>Install Sandisk Assistant</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")

        desc = Gtk.Label(
            label=ballmerize(
                "Press Install to continue.\n"
                "But seriously, you don’t need this software."
            )
        )
        desc.set_wrap(True)
        desc.set_xalign(0.0)
        desc.add_css_class("wizard-body")

        box.append(title)
        box.append(desc)

        self.stack.add_titled(box, "install", "Install")
        self.page_ids.append("install")
        self.page_titles.append("Install")

    def show_page(self, index):
        self.current_index = index
        self.stack.set_visible_child_name(self.page_ids[index])
        self.update_buttons()
        self.update_sidebar_selection()

    def update_buttons(self):
        page = self.page_ids[self.current_index]

        if page == "welcome":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)

        elif page == "install":
            self.back_button.set_sensitive(True)
            self.next_button.set_label("Install")
            self.cancel_button.set_sensitive(True)

    def on_back_clicked(self, button):
        if self.current_index > 0:
            self.show_page(self.current_index - 1)

    def on_next_clicked(self, button):
        page = self.page_ids[self.current_index]

        if page == "welcome":
            self.show_page(self.current_index + 1)

        elif page == "install":
            dialog = Gtk.AlertDialog(
                message=ballmerize("No Installation Needed"),
                detail=ballmerize(
                    "You don’t need Sandisk Assistant. Just close the installer."
                ),
                buttons=[ballmerize("OK")],
            )

            def on_done(d, result):
                d.choose_finish(result)
                # nothing else, just close

            dialog.choose(self, None, on_done)

    def on_cancel_clicked(self, button):
        self.close()


# ---------------------- Windows malware joke installer ----------------------


class JokeInstallerWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.connect("close-request", lambda *a: self.app.quit())
        self.app = app
        self.set_title("Windows Malware Setup (Just Kidding)")
        self.set_default_size(600, -1)
        self.set_resizable(False)

        self.install_started = False
        self.install_finished = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Windows Malware Setup (Fake)"))
        self.set_titlebar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(content)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sidebar.set_margin_top(16)
        sidebar.set_margin_bottom(16)
        sidebar.set_margin_start(16)
        sidebar.set_margin_end(0)
        sidebar.add_css_class("sidebar")
        content.append(sidebar)

        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        icon.set_pixel_size(48)
        sidebar.append(icon)

        steps_label = Gtk.Label(label="Steps")
        steps_label.set_xalign(0.0)
        steps_label.add_css_class("wizard-title")
        sidebar.append(steps_label)

        self.steps_list = Gtk.ListBox()
        self.steps_list.set_selection_mode(Gtk.SelectionMode.NONE)
        sidebar.append(self.steps_list)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.set_margin_top(16)
        self.stack.set_margin_bottom(16)
        self.stack.set_margin_start(0)
        self.stack.set_margin_end(16)
        content.append(self.stack)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(separator)

        button_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_panel.set_margin_top(6)
        button_panel.set_margin_bottom(6)
        button_panel.set_margin_start(12)
        button_panel.set_margin_end(12)
        root.append(button_panel)

        spacer = Gtk.Box()
        button_panel.append(spacer)

        self.back_button = Gtk.Button(label="Back")
        self.next_button = Gtk.Button(label="Next")
        self.cancel_button = Gtk.Button(label="Cancel")

        button_panel.append(self.back_button)
        button_panel.append(self.next_button)
        button_panel.append(self.cancel_button)

        self.back_button.connect("clicked", self.on_back_clicked)
        self.next_button.connect("clicked", self.on_next_clicked)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)

        self.page_ids = []
        self.page_titles = []
        self.current_index = 0

        self.build_pages()
        self.build_sidebar_steps()
        self.show_page(0)
        self.apply_css()

    def apply_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            .wizard-title {
                font-size: 18px;
                font-weight: bold;
            }
            .wizard-body {
                font-size: 14px;
            }
            button {
                padding: 8px 18px;
                font-size: 14px;
            }
            progressbar {
                min-height: 12px;
            }
            textview, textview text {
                font-family: monospace;
                font-size: 14px;
            }
            textview {
                border: 1px solid @borders;
                border-radius: 4px;
                padding: 6px;
            }
            .sidebar {
                border-right: 1px solid @borders;
                padding-right: 12px;
            }
            .step-row.selected {
                background-color: @accent_bg_color;
                color: @accent_fg_color;
            }
        """
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_pages(self):
        self.build_welcome_page()
        self.build_prompts_page()
        self.build_fake_install_page()
        self.build_finish_page()

    def build_sidebar_steps(self):
        self.steps_list.remove_all()
        for idx, title in enumerate(self.page_titles):
            row = Gtk.ListBoxRow()
            row.add_css_class("step-row")
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            box.set_margin_start(4)
            box.set_margin_end(4)

            icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
            icon.set_pixel_size(16)
            box.append(icon)

            label = Gtk.Label(label=title)
            label.set_xalign(0.0)
            box.append(label)

            row.set_child(box)
            self.steps_list.append(row)

        self.update_sidebar_selection()

    def update_sidebar_selection(self):
        for i, row in enumerate(self.steps_list):
            if i == self.current_index:
                row.add_css_class("selected")
            else:
                row.remove_css_class("selected")

    def build_welcome_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup(
            "<span size='large' weight='bold'>Welcome to the Totally Legit Windows Malware Setup</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")

        desc = Gtk.Label(
            label=ballmerize(
                "Good news: you cannot actually install Windows malware on Linux this way.\n"
                "But we can pretend, for nostalgia and chaos."
            )
        )
        desc.set_wrap(True)
        desc.set_xalign(0.0)
        desc.add_css_class("wizard-body")

        info = Gtk.Label(
            label=ballmerize(
                "This is a joke installer. Nothing will be installed.\n"
                "Click Next to continue the bit."
            )
        )
        info.set_wrap(True)
        info.set_xalign(0.0)
        info.add_css_class("wizard-body")

        box.append(title)
        box.append(desc)
        box.append(info)

        self.stack.add_titled(box, "welcome", "Welcome")
        self.page_ids.append("welcome")
        self.page_titles.append("Welcome")

    def build_prompts_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup(
            "<span size='large' weight='bold'>Additional Totally Necessary Prompts</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        prompts = [
            "• Do you agree to install 17 toolbars? (This does nothing.)",
            "• Do you accept that your cursor may turn into a spinning ad? (Also fake.)",
            "• Do you want to set your homepage to 'http://not-a-real-malware-site.local'? (Still fake.)",
        ]

        for p in prompts:
            lbl = Gtk.Label(label=ballmerize(p))
            lbl.set_wrap(True)
            lbl.set_xalign(0.0)
            lbl.add_css_class("wizard-body")
            box.append(lbl)

        note = Gtk.Label(
            label=ballmerize(
                "Clicking any button here will not install anything.\n"
                "You're safe. Linux is safe. Your vibe is safe."
            )
        )
        note.set_wrap(True)
        note.set_xalign(0.0)
        note.add_css_class("wizard-body")
        box.append(note)

        self.stack.add_titled(box, "prompts", "Prompts")
        self.page_ids.append("prompts")
        self.page_titles.append("Prompts")

    def build_fake_install_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(24)
        outer.set_margin_bottom(24)
        outer.set_margin_start(24)
        outer.set_margin_end(24)

        label = Gtk.Label(
            label=ballmerize(
                "Ready to pretend to install Windows malware.\n"
                "Click Install to watch a fake progress bar."
            )
        )
        label.set_xalign(0.0)
        label.add_css_class("wizard-body")

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)

        self.output_buffer = Gtk.TextBuffer()
        textview = Gtk.TextView(buffer=self.output_buffer)
        textview.set_editable(False)
        textview.set_monospace(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(200)
        scrolled.set_child(textview)

        outer.append(label)
        outer.append(self.progress)
        outer.append(scrolled)

        self.stack.add_titled(outer, "install", "Install")
        self.page_ids.append("install")
        self.page_titles.append("Install")

    def build_finish_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self.finish_title = Gtk.Label()
        self.finish_title.set_markup(
            "<span size='large' weight='bold'>All Done (Nothing Happened)</span>"
        )
        self.finish_title.set_xalign(0.0)
        self.finish_title.add_css_class("wizard-title")

        self.finish_label = Gtk.Label(
            label=ballmerize(
                "No malware was installed.\n"
                "Linux remains unbothered, untouched, and unbloatwared."
            )
        )
        self.finish_label.set_wrap(True)
        self.finish_label.set_xalign(0.0)
        self.finish_label.add_css_class("wizard-body")

        box.append(self.finish_title)
        box.append(self.finish_label)

        self.stack.add_titled(box, "finish", "Finish")
        self.page_ids.append("finish")
        self.page_titles.append("Finish")

    def show_page(self, index):
        self.current_index = index
        self.stack.set_visible_child_name(self.page_ids[index])
        self.update_buttons()
        self.update_sidebar_selection()

    def update_buttons(self):
        page_id = self.page_ids[self.current_index]

        if page_id == "welcome":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id == "prompts":
            self.back_button.set_sensitive(True)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id == "install":
            self.back_button.set_sensitive(not self.install_started)
            if not self.install_started:
                self.next_button.set_label("Install")
                self.next_button.set_sensitive(True)
            else:
                self.next_button.set_label("Installing...")
                self.next_button.set_sensitive(False)
            self.cancel_button.set_sensitive(not self.install_started)
        elif page_id == "finish":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Finish")
            self.next_button.set_sensitive(True)
            self.cancel_button.set_sensitive(False)

    def on_back_clicked(self, button):
        if self.current_index > 0:
            self.show_page(self.current_index - 1)

    def on_next_clicked(self, button):
        page_id = self.page_ids[self.current_index]
        if page_id in ("welcome", "prompts"):
            self.show_page(self.current_index + 1)
        elif page_id == "install":
            if not self.install_started:
                self.start_fake_install()
        elif page_id == "finish":
            self.close()

    def on_cancel_clicked(self, button):
        self.close()

    def append_output(self, text):
        text = ballmerize(text)
        end = self.output_buffer.get_end_iter()
        self.output_buffer.insert(end, text)

    def start_fake_install(self):
        self.install_started = True
        self.update_buttons()
        self.append_output("Initializing fake malware installer...\n")
        self.progress.set_text(ballmerize("Pretending to install..."))

        def step_progress(step=[0]):
            if step[0] >= 10:
                self.install_finished = True
                self.progress.set_fraction(1.0)
                self.progress.set_text(ballmerize("Completed (Fake)"))
                self.append_output(
                    ballmerize("Done. Absolutely nothing was installed.\n")
                )
                self.show_page(self.page_ids.index("finish"))
                return False
            step[0] += 1
            self.progress.set_fraction(step[0] / 10.0)
            self.append_output(ballmerize(f"Fake step {step[0]} of 10...\n"))
            return True

        GLib.timeout_add(300, step_progress)


# ---------------------- WD Assistant joke installer ----------------------


class WDJokeInstallerWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.connect("close-request", lambda *a: self.app.quit())
        self.app = app
        self.set_title("WD Assistant Setup (Fake)")
        self.set_default_size(600, -1)
        self.set_resizable(False)

        self.install_started = False
        self.install_finished = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="WD Assistant Setup (Fake)"))
        self.set_titlebar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(content)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sidebar.set_margin_top(16)
        sidebar.set_margin_bottom(16)
        sidebar.set_margin_start(16)
        sidebar.set_margin_end(0)
        sidebar.add_css_class("sidebar")
        content.append(sidebar)

        icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
        icon.set_pixel_size(48)
        sidebar.append(icon)

        steps_label = Gtk.Label(label="Steps")
        steps_label.set_xalign(0.0)
        steps_label.add_css_class("wizard-title")
        sidebar.append(steps_label)

        self.steps_list = Gtk.ListBox()
        self.steps_list.set_selection_mode(Gtk.SelectionMode.NONE)
        sidebar.append(self.steps_list)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.set_margin_top(16)
        self.stack.set_margin_bottom(16)
        self.stack.set_margin_start(0)
        self.stack.set_margin_end(16)
        content.append(self.stack)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(separator)

        button_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_panel.set_margin_top(6)
        button_panel.set_margin_bottom(6)
        button_panel.set_margin_start(12)
        button_panel.set_margin_end(12)
        root.append(button_panel)

        spacer = Gtk.Box()
        button_panel.append(spacer)

        self.back_button = Gtk.Button(label="Back")
        self.next_button = Gtk.Button(label="Next")
        self.cancel_button = Gtk.Button(label="Cancel")

        button_panel.append(self.back_button)
        button_panel.append(self.next_button)
        button_panel.append(self.cancel_button)

        self.back_button.connect("clicked", self.on_back_clicked)
        self.next_button.connect("clicked", self.on_next_clicked)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)

        self.page_ids = []
        self.page_titles = []
        self.current_index = 0

        self.build_pages()
        self.build_sidebar_steps()
        self.show_page(0)
        self.apply_css()

    def apply_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            .wizard-title {
                font-size: 18px;
                font-weight: bold;
            }
            .wizard-body {
                font-size: 14px;
            }
            button {
                padding: 8px 18px;
                font-size: 14px;
            }
            progressbar {
                min-height: 12px;
            }
            textview, textview text {
                font-family: monospace;
                font-size: 14px;
            }
            textview {
                border: 1px solid @borders;
                border-radius: 4px;
                padding: 6px;
            }
            .sidebar {
                border-right: 1px solid @borders;
                padding-right: 12px;
            }
            .step-row.selected {
                background-color: @accent_bg_color;
                color: @accent_fg_color;
            }
        """
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_pages(self):
        self.build_welcome_page()
        self.build_optimize_page()
        self.build_backup_page()
        self.build_install_page()
        self.build_finish_page()

    def build_sidebar_steps(self):
        self.steps_list.remove_all()
        for idx, title in enumerate(self.page_titles):
            row = Gtk.ListBoxRow()
            row.add_css_class("step-row")
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            box.set_margin_start(4)
            box.set_margin_end(4)

            icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
            icon.set_pixel_size(16)
            box.append(icon)

            label = Gtk.Label(label=title)
            label.set_xalign(0.0)
            box.append(label)

            row.set_child(box)
            self.steps_list.append(row)

        self.update_sidebar_selection()

    def update_sidebar_selection(self):
        for i, row in enumerate(self.steps_list):
            if i == self.current_index:
                row.add_css_class("selected")
            else:
                row.remove_css_class("selected")

    def build_welcome_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup(
            "<span size='large' weight='bold'>Welcome to WD Assistant Setup (Fake)</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")

        desc = Gtk.Label(
            label=ballmerize(
                "WD Assistant claims to optimize and manage your drive.\n"
                "On Linux, your drive is already fine."
            )
        )
        desc.set_wrap(True)
        desc.set_xalign(0.0)
        desc.add_css_class("wizard-body")

        info = Gtk.Label(
            label=ballmerize(
                "This is a joke installer. Nothing will be installed.\n"
                "Click Next to continue."
            )
        )
        info.set_wrap(True)
        info.set_xalign(0.0)
        info.add_css_class("wizard-body")

        box.append(title)
        box.append(desc)
        box.append(info)

        self.stack.add_titled(box, "welcome", "Welcome")
        self.page_ids.append("welcome")
        self.page_titles.append("Welcome")

    def build_optimize_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>Drive Optimization</span>")
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        text = Gtk.Label(
            label=ballmerize(
                "WD Assistant would like to 'optimize' your drive.\n"
                "On Linux, the filesystem and kernel already do that."
            )
        )
        text.set_wrap(True)
        text.set_xalign(0.0)
        text.add_css_class("wizard-body")
        box.append(text)

        self.stack.add_titled(box, "optimize", "Drive Optimization")
        self.page_ids.append("optimize")
        self.page_titles.append("Drive Optimization")

    def build_backup_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>Backup Scheduling</span>")
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        text = Gtk.Label(
            label=ballmerize(
                "WD Assistant wants to schedule backups.\n"
                "You can already use rsync, borg, or any backup tool you like."
            )
        )
        text.set_wrap(True)
        text.set_xalign(0.0)
        text.add_css_class("wizard-body")
        box.append(text)

        self.stack.add_titled(box, "backup", "Backup Scheduling")
        self.page_ids.append("backup")
        self.page_titles.append("Backup Scheduling")

    def build_install_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(24)
        outer.set_margin_bottom(24)
        outer.set_margin_start(24)
        outer.set_margin_end(24)

        label = Gtk.Label(
            label=ballmerize(
                "Ready to install WD Assistant.\n"
                "Click Install to pretend to install it."
            )
        )
        label.set_xalign(0.0)
        label.add_css_class("wizard-body")

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)

        self.output_buffer = Gtk.TextBuffer()
        textview = Gtk.TextView(buffer=self.output_buffer)
        textview.set_editable(False)
        textview.set_monospace(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(200)
        scrolled.set_child(textview)

        outer.append(label)
        outer.append(self.progress)
        outer.append(scrolled)

        self.stack.add_titled(outer, "install", "Install WD Assistant")
        self.page_ids.append("install")
        self.page_titles.append("Install WD Assistant")

    def build_finish_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self.finish_title = Gtk.Label()
        self.finish_title.set_markup(
            "<span size='large' weight='bold'>All Done (Nothing Installed)</span>"
        )
        self.finish_title.set_xalign(0.0)
        self.finish_title.add_css_class("wizard-title")

        self.finish_label = Gtk.Label(
            label=ballmerize(
                "No WD Assistant was installed.\n"
                "Linux already manages your drive just fine."
            )
        )
        self.finish_label.set_wrap(True)
        self.finish_label.set_xalign(0.0)
        self.finish_label.add_css_class("wizard-body")

        box.append(self.finish_title)
        box.append(self.finish_label)

        self.stack.add_titled(box, "finish", "Finish")
        self.page_ids.append("finish")
        self.page_titles.append("Finish")

    def show_page(self, index):
        self.current_index = index
        self.stack.set_visible_child_name(self.page_ids[index])
        self.update_buttons()
        self.update_sidebar_selection()

    def update_buttons(self):
        page_id = self.page_ids[self.current_index]

        if page_id == "welcome":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id in ("optimize", "backup"):
            self.back_button.set_sensitive(True)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id == "install":
            self.back_button.set_sensitive(not self.install_started)
            if not self.install_started:
                self.next_button.set_label("Install")
                self.next_button.set_sensitive(True)
            else:
                self.next_button.set_label("Installing...")
                self.next_button.set_sensitive(False)
            self.cancel_button.set_sensitive(not self.install_started)
        elif page_id == "finish":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Finish")
            self.next_button.set_sensitive(True)
            self.cancel_button.set_sensitive(False)

    def on_back_clicked(self, button):
        if self.current_index > 0:
            self.show_page(self.current_index - 1)

    def on_next_clicked(self, button):
        page_id = self.page_ids[self.current_index]
        if page_id in ("welcome", "optimize", "backup"):
            self.show_page(self.current_index + 1)
        elif page_id == "install":
            if not self.install_started:
                self.start_fake_install()
        elif page_id == "finish":
            self.close()

    def on_cancel_clicked(self, button):
        self.close()

    def append_output(self, text):
        text = ballmerize(text)
        end = self.output_buffer.get_end_iter()
        self.output_buffer.insert(end, text)

    def start_fake_install(self):
        self.install_started = True
        self.update_buttons()
        self.append_output("Starting fake WD Assistant installation...\n")
        self.progress.set_text(ballmerize("Pretending to install..."))

        def step_progress(step=[0]):
            if step[0] >= 8:
                self.install_finished = True
                self.progress.set_fraction(1.0)
                self.progress.set_text(ballmerize("Completed (Fake)"))
                self.append_output(
                    ballmerize(
                        "Done. WD Assistant was not actually installed.\n"
                        "You don't need it on Linux.\n"
                    )
                )
                self.show_page(self.page_ids.index("finish"))
                return False
            step[0] += 1
            self.progress.set_fraction(step[0] / 8.0)
            self.append_output(ballmerize(f"Fake step {step[0]} of 8...\n"))
            return True

        GLib.timeout_add(300, step_progress)


# ---------------------- Seagate Dashboard joke installer ----------------------


class SeagateDashboardJokeInstallerWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.connect("close-request", lambda *a: self.app.quit())
        self.app = app
        self.set_title("Seagate Dashboard Setup (Fake)")
        self.set_default_size(600, -1)
        self.set_resizable(False)

        self.install_started = False
        self.install_finished = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Seagate Dashboard Setup (Fake)"))
        self.set_titlebar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(content)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sidebar.set_margin_top(16)
        sidebar.set_margin_bottom(16)
        sidebar.set_margin_start(16)
        sidebar.set_margin_end(0)
        sidebar.add_css_class("sidebar")
        content.append(sidebar)

        icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
        icon.set_pixel_size(48)
        sidebar.append(icon)

        steps_label = Gtk.Label(label="Steps")
        steps_label.set_xalign(0.0)
        steps_label.add_css_class("wizard-title")
        sidebar.append(steps_label)

        self.steps_list = Gtk.ListBox()
        self.steps_list.set_selection_mode(Gtk.SelectionMode.NONE)
        sidebar.append(self.steps_list)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.set_margin_top(16)
        self.stack.set_margin_bottom(16)
        self.stack.set_margin_start(0)
        self.stack.set_margin_end(16)
        content.append(self.stack)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(separator)

        button_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_panel.set_margin_top(6)
        button_panel.set_margin_bottom(6)
        button_panel.set_margin_start(12)
        button_panel.set_margin_end(12)
        root.append(button_panel)

        spacer = Gtk.Box()
        button_panel.append(spacer)

        self.back_button = Gtk.Button(label="Back")
        self.next_button = Gtk.Button(label="Next")
        self.cancel_button = Gtk.Button(label="Cancel")

        button_panel.append(self.back_button)
        button_panel.append(self.next_button)
        button_panel.append(self.cancel_button)

        self.back_button.connect("clicked", self.on_back_clicked)
        self.next_button.connect("clicked", self.on_next_clicked)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)

        self.page_ids = []
        self.page_titles = []
        self.current_index = 0

        self.build_pages()
        self.build_sidebar_steps()
        self.show_page(0)
        self.apply_css()

    def apply_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            .wizard-title {
                font-size: 18px;
                font-weight: bold;
            }
            .wizard-body {
                font-size: 14px;
            }
            button {
                padding: 8px 18px;
                font-size: 14px;
            }
            progressbar {
                min-height: 12px;
            }
            textview, textview text {
                font-family: monospace;
                font-size: 14px;
            }
            textview {
                border: 1px solid @borders;
                border-radius: 4px;
                padding: 6px;
            }
            .sidebar {
                border-right: 1px solid @borders;
                padding-right: 12px;
            }
            .step-row.selected {
                background-color: @accent_bg_color;
                color: @accent_fg_color;
            }
        """
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_pages(self):
        self.build_welcome_page()
        self.build_dashboard_page()
        self.build_cloud_page()
        self.build_install_page()
        self.build_finish_page()

    def build_sidebar_steps(self):
        self.steps_list.remove_all()
        for idx, title in enumerate(self.page_titles):
            row = Gtk.ListBoxRow()
            row.add_css_class("step-row")
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            box.set_margin_start(4)
            box.set_margin_end(4)

            icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
            icon.set_pixel_size(16)
            box.append(icon)

            label = Gtk.Label(label=title)
            label.set_xalign(0.0)
            box.append(label)

            row.set_child(box)
            self.steps_list.append(row)

        self.update_sidebar_selection()

    def update_sidebar_selection(self):
        for i, row in enumerate(self.steps_list):
            if i == self.current_index:
                row.add_css_class("selected")
            else:
                row.remove_css_class("selected")

    def build_welcome_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup(
            "<span size='large' weight='bold'>Welcome to Seagate Dashboard Setup (Fake)</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")

        desc = Gtk.Label(
            label=ballmerize(
                "Seagate Dashboard claims to monitor and manage your drive.\n"
                "On Linux, SMART and your tools already do that."
            )
        )
        desc.set_wrap(True)
        desc.set_xalign(0.0)
        desc.add_css_class("wizard-body")

        info = Gtk.Label(
            label=ballmerize(
                "This is a joke installer. Nothing will be installed.\n"
                "Click Next to continue."
            )
        )
        info.set_wrap(True)
        info.set_xalign(0.0)
        info.add_css_class("wizard-body")

        box.append(title)
        box.append(desc)
        box.append(info)

        self.stack.add_titled(box, "welcome", "Welcome")
        self.page_ids.append("welcome")
        self.page_titles.append("Welcome")

    def build_dashboard_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>Dashboard Preview</span>")
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        text = Gtk.Label(
            label=ballmerize(
                "Seagate Dashboard would show you graphs, charts, and health indicators.\n"
                "On Linux, you can already use smartctl, gnome-disks, or other tools."
            )
        )
        text.set_wrap(True)
        text.set_xalign(0.0)
        text.add_css_class("wizard-body")
        box.append(text)

        self.stack.add_titled(box, "dashboard", "Dashboard Preview")
        self.page_ids.append("dashboard")
        self.page_titles.append("Dashboard Preview")

    def build_cloud_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>Cloud Backup Options</span>")
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        text = Gtk.Label(
            label=ballmerize(
                "Seagate Dashboard wants to back up your data to the cloud.\n"
                "You can already choose any backup solution you trust on Linux."
            )
        )
        text.set_wrap(True)
        text.set_xalign(0.0)
        text.add_css_class("wizard-body")
        box.append(text)

        self.stack.add_titled(box, "cloud", "Cloud Backup Options")
        self.page_ids.append("cloud")
        self.page_titles.append("Cloud Backup Options")

    def build_install_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(24)
        outer.set_margin_bottom(24)
        outer.set_margin_start(24)
        outer.set_margin_end(24)

        label = Gtk.Label(
            label=ballmerize(
                "Ready to install Seagate Dashboard.\n"
                "Click Install to pretend to install it."
            )
        )
        label.set_xalign(0.0)
        label.add_css_class("wizard-body")

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)

        self.output_buffer = Gtk.TextBuffer()
        textview = Gtk.TextView(buffer=self.output_buffer)
        textview.set_editable(False)
        textview.set_monospace(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(200)
        scrolled.set_child(textview)

        outer.append(label)
        outer.append(self.progress)
        outer.append(scrolled)

        self.stack.add_titled(outer, "install", "Install Dashboard")
        self.page_ids.append("install")
        self.page_titles.append("Install Dashboard")

    def build_finish_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self.finish_title = Gtk.Label()
        self.finish_title.set_markup(
            "<span size='large' weight='bold'>All Done (Nothing Installed)</span>"
        )
        self.finish_title.set_xalign(0.0)
        self.finish_title.add_css_class("wizard-title")

        self.finish_label = Gtk.Label(
            label=ballmerize(
                "No Seagate Dashboard was installed.\n"
                "Linux already provides the tools you need."
            )
        )
        self.finish_label.set_wrap(True)
        self.finish_label.set_xalign(0.0)
        self.finish_label.add_css_class("wizard-body")

        box.append(self.finish_title)
        box.append(self.finish_label)

        self.stack.add_titled(box, "finish", "Finish")
        self.page_ids.append("finish")
        self.page_titles.append("Finish")

    def show_page(self, index):
        self.current_index = index
        self.stack.set_visible_child_name(self.page_ids[index])
        self.update_buttons()
        self.update_sidebar_selection()

    def update_buttons(self):
        page_id = self.page_ids[self.current_index]

        if page_id == "welcome":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id in ("dashboard", "cloud"):
            self.back_button.set_sensitive(True)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id == "install":
            self.back_button.set_sensitive(not self.install_started)
            if not self.install_started:
                self.next_button.set_label("Install")
                self.next_button.set_sensitive(True)
            else:
                self.next_button.set_label("Installing...")
                self.next_button.set_sensitive(False)
            self.cancel_button.set_sensitive(not self.install_started)
        elif page_id == "finish":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Finish")
            self.next_button.set_sensitive(True)
            self.cancel_button.set_sensitive(False)

    def on_back_clicked(self, button):
        if self.current_index > 0:
            self.show_page(self.current_index - 1)

    def on_next_clicked(self, button):
        page_id = self.page_ids[self.current_index]
        if page_id in ("welcome", "dashboard", "cloud"):
            self.show_page(self.current_index + 1)
        elif page_id == "install":
            if not self.install_started:
                self.start_fake_install()
        elif page_id == "finish":
            self.close()

    def on_cancel_clicked(self, button):
        self.close()

    def append_output(self, text):
        text = ballmerize(text)
        end = self.output_buffer.get_end_iter()
        self.output_buffer.insert(end, text)

    def start_fake_install(self):
        self.install_started = True
        self.update_buttons()
        self.append_output("Starting fake Seagate Dashboard installation...\n")
        self.progress.set_text(ballmerize("Pretending to install..."))

        def step_progress(step=[0]):
            if step[0] >= 8:
                self.install_finished = True
                self.progress.set_fraction(1.0)
                self.progress.set_text(ballmerize("Completed (Fake)"))
                self.append_output(
                    ballmerize(
                        "Done. Seagate Dashboard was not actually installed.\n"
                        "You don't need it on Linux.\n"
                    )
                )
                self.show_page(self.page_ids.index("finish"))
                return False
            step[0] += 1
            self.progress.set_fraction(step[0] / 8.0)
            self.append_output(ballmerize(f"Fake step {step[0]} of 8...\n"))
            return True

        GLib.timeout_add(300, step_progress)


# ---------------------- RGB Gaming Mouse Driver joke installer ----------------------


class RGBMouseJokeInstallerWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.connect("close-request", lambda *a: self.app.quit())
        self.app = app
        self.set_title("RGB Gaming Mouse Driver Installer (Fake)")
        self.set_default_size(600, -1)
        self.set_resizable(False)

        self.install_started = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(
            Gtk.Label(label="RGB Gaming Mouse Driver Installer (Fake)")
        )
        self.set_titlebar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(content)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sidebar.set_margin_top(16)
        sidebar.set_margin_bottom(16)
        sidebar.set_margin_start(16)
        sidebar.set_margin_end(0)
        sidebar.add_css_class("sidebar")
        content.append(sidebar)

        icon = Gtk.Image.new_from_icon_name("input-mouse-symbolic")
        icon.set_pixel_size(48)
        sidebar.append(icon)

        steps_label = Gtk.Label(label="Steps")
        steps_label.set_xalign(0.0)
        steps_label.add_css_class("wizard-title")
        sidebar.append(steps_label)

        self.steps_list = Gtk.ListBox()
        self.steps_list.set_selection_mode(Gtk.SelectionMode.NONE)
        sidebar.append(self.steps_list)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.set_margin_top(16)
        self.stack.set_margin_bottom(16)
        self.stack.set_margin_start(0)
        self.stack.set_margin_end(16)
        content.append(self.stack)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(separator)

        button_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_panel.set_margin_top(6)
        button_panel.set_margin_bottom(6)
        button_panel.set_margin_start(12)
        button_panel.set_margin_end(12)
        root.append(button_panel)

        spacer = Gtk.Box()
        button_panel.append(spacer)

        self.back_button = Gtk.Button(label="Back")
        self.next_button = Gtk.Button(label="Next")
        self.cancel_button = Gtk.Button(label="Cancel")

        button_panel.append(self.back_button)
        button_panel.append(self.next_button)
        button_panel.append(self.cancel_button)

        self.back_button.connect("clicked", self.on_back_clicked)
        self.next_button.connect("clicked", self.on_next_clicked)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)

        self.page_ids = []
        self.page_titles = []
        self.current_index = 0

        self.build_pages()
        self.build_sidebar_steps()
        self.show_page(0)
        self.apply_css()

    def apply_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            .wizard-title {
                font-size: 18px;
                font-weight: bold;
            }
            .wizard-body {
                font-size: 14px;
            }
            button {
                padding: 8px 18px;
                font-size: 14px;
            }
            .sidebar {
                border-right: 1px solid @borders;
                padding-right: 12px;
            }
            .step-row.selected {
                background-color: @accent_bg_color;
                color: @accent_fg_color;
            }
        """
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_pages(self):
        self.build_welcome_page()
        self.build_lighting_page()
        self.build_install_page()
        self.build_finish_page()

    def build_sidebar_steps(self):
        self.steps_list.remove_all()
        for idx, title in enumerate(self.page_titles):
            row = Gtk.ListBoxRow()
            row.add_css_class("step-row")
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            box.set_margin_start(4)
            box.set_margin_end(4)

            icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
            icon.set_pixel_size(16)
            box.append(icon)

            label = Gtk.Label(label=title)
            label.set_xalign(0.0)
            box.append(label)

            row.set_child(box)
            self.steps_list.append(row)

        self.update_sidebar_selection()

    def update_sidebar_selection(self):
        for i, row in enumerate(self.steps_list):
            if i == self.current_index:
                row.add_css_class("selected")
            else:
                row.remove_css_class("selected")

    def build_welcome_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup(
            "<span size='large' weight='bold'>Welcome to RGB Gaming Mouse Driver Installer (Fake)</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")

        desc = Gtk.Label(
            label=ballmerize(
                "Unlock 16.8 million colors, macros, and more.\n"
                "Except this is Linux, and your mouse already works."
            )
        )
        desc.set_wrap(True)
        desc.set_xalign(0.0)
        desc.add_css_class("wizard-body")

        info = Gtk.Label(
            label=ballmerize(
                "This is a joke installer. Nothing will be installed.\n"
                "Click Next to continue."
            )
        )
        info.set_wrap(True)
        info.set_xalign(0.0)
        info.add_css_class("wizard-body")

        box.append(title)
        box.append(desc)
        box.append(info)

        self.stack.add_titled(box, "welcome", "Welcome")
        self.page_ids.append("welcome")
        self.page_titles.append("Welcome")

    def build_lighting_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>Lighting Effects</span>")
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        text = Gtk.Label(
            label=ballmerize(
                "Choose from fake lighting modes:\n"
                "• Breathing\n"
                "• Wave\n"
                "• Unicorn Vomit\n"
                "None of these will actually change your mouse."
            )
        )
        text.set_wrap(True)
        text.set_xalign(0.0)
        text.add_css_class("wizard-body")
        box.append(text)

        self.stack.add_titled(box, "lighting", "Lighting Effects")
        self.page_ids.append("lighting")
        self.page_titles.append("Lighting Effects")

    def build_install_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>Install RGB Driver</span>")
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        text = Gtk.Label(
            label=ballmerize(
                "Click Install to attempt to install proprietary RGB drivers.\n"
                "On Linux, you don't actually need them for basic mouse functionality."
            )
        )
        text.set_wrap(True)
        text.set_xalign(0.0)
        text.add_css_class("wizard-body")
        box.append(text)

        self.stack.add_titled(box, "install", "Install RGB Driver")
        self.page_ids.append("install")
        self.page_titles.append("Install RGB Driver")

    def build_finish_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self.finish_title = Gtk.Label()
        self.finish_title.set_markup(
            "<span size='large' weight='bold'>All Done (Nothing Installed)</span>"
        )
        self.finish_title.set_xalign(0.0)
        self.finish_title.add_css_class("wizard-title")

        self.finish_label = Gtk.Label(
            label=ballmerize(
                "No RGB drivers were installed.\n"
                "Your mouse still works just fine on Linux."
            )
        )
        self.finish_label.set_wrap(True)
        self.finish_label.set_xalign(0.0)
        self.finish_label.add_css_class("wizard-body")

        box.append(self.finish_title)
        box.append(self.finish_label)

        self.stack.add_titled(box, "finish", "Finish")
        self.page_ids.append("finish")
        self.page_titles.append("Finish")

    def show_page(self, index):
        self.current_index = index
        self.stack.set_visible_child_name(self.page_ids[index])
        self.update_buttons()
        self.update_sidebar_selection()

    def update_buttons(self):
        page_id = self.page_ids[self.current_index]

        if page_id == "welcome":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id == "lighting":
            self.back_button.set_sensitive(True)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id == "install":
            self.back_button.set_sensitive(True)
            self.next_button.set_label("Install")
            self.cancel_button.set_sensitive(True)
        elif page_id == "finish":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Finish")
            self.next_button.set_sensitive(True)
            self.cancel_button.set_sensitive(False)

    def on_back_clicked(self, button):
        if self.current_index > 0:
            self.show_page(self.current_index - 1)

    def on_next_clicked(self, button):
        page_id = self.page_ids[self.current_index]
        if page_id in ("welcome", "lighting"):
            self.show_page(self.current_index + 1)
        elif page_id == "install":
            self.show_refusal_dialog()
        elif page_id == "finish":
            self.close()

    def on_cancel_clicked(self, button):
        self.close()

    def show_refusal_dialog(self):
        dialog = Gtk.AlertDialog(
            message=ballmerize("No Drivers Needed"),
            detail=ballmerize(
                "Linux does not require proprietary RGB mouse drivers for basic functionality.\n"
                "Use open-source tools if you really want to tweak lighting."
            ),
            buttons=[ballmerize("OK")],
        )

        def on_done(d, result):
            d.choose_finish(result)
            self.show_page(self.page_ids.index("finish"))

        dialog.choose(self, None, on_done)


# ---------------------- Printer Setup Wizard joke installer ----------------------


class PrinterSetupJokeInstallerWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.connect("close-request", lambda *a: self.app.quit())
        self.app = app
        self.set_title("Printer Setup Wizard (Fake)")
        self.set_default_size(600, -1)
        self.set_resizable(False)

        self.crashed = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Printer Setup Wizard (Fake)"))
        self.set_titlebar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(content)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sidebar.set_margin_top(16)
        sidebar.set_margin_bottom(16)
        sidebar.set_margin_start(16)
        sidebar.set_margin_end(0)
        sidebar.add_css_class("sidebar")
        content.append(sidebar)

        icon = Gtk.Image.new_from_icon_name("printer-symbolic")
        icon.set_pixel_size(48)
        sidebar.append(icon)

        steps_label = Gtk.Label(label="Steps")
        steps_label.set_xalign(0.0)
        steps_label.add_css_class("wizard-title")
        sidebar.append(steps_label)

        self.steps_list = Gtk.ListBox()
        self.steps_list.set_selection_mode(Gtk.SelectionMode.NONE)
        sidebar.append(self.steps_list)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.set_margin_top(16)
        self.stack.set_margin_bottom(16)
        self.stack.set_margin_start(0)
        self.stack.set_margin_end(16)
        content.append(self.stack)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(separator)

        button_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_panel.set_margin_top(6)
        button_panel.set_margin_bottom(6)
        button_panel.set_margin_start(12)
        button_panel.set_margin_end(12)
        root.append(button_panel)

        spacer = Gtk.Box()
        button_panel.append(spacer)

        self.back_button = Gtk.Button(label="Back")
        self.next_button = Gtk.Button(label="Next")
        self.cancel_button = Gtk.Button(label="Cancel")

        button_panel.append(self.back_button)
        button_panel.append(self.next_button)
        button_panel.append(self.cancel_button)

        self.back_button.connect("clicked", self.on_back_clicked)
        self.next_button.connect("clicked", self.on_next_clicked)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)

        self.page_ids = []
        self.page_titles = []
        self.current_index = 0

        self.build_pages()
        self.build_sidebar_steps()
        self.show_page(0)
        self.apply_css()

    def apply_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            .wizard-title {
                font-size: 18px;
                font-weight: bold;
            }
            .wizard-body {
                font-size: 14px;
            }
            button {
                padding: 8px 18px;
                font-size: 14px;
            }
            .sidebar {
                border-right: 1px solid @borders;
                padding-right: 12px;
            }
            .step-row.selected {
                background-color: @accent_bg_color;
                color: @accent_fg_color;
            }
        """
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_pages(self):
        self.build_welcome_page()
        self.build_search_page()
        self.build_install_page()
        self.build_finish_page()

    def build_sidebar_steps(self):
        self.steps_list.remove_all()
        for idx, title in enumerate(self.page_titles):
            row = Gtk.ListBoxRow()
            row.add_css_class("step-row")
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            box.set_margin_start(4)
            box.set_margin_end(4)

            icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
            icon.set_pixel_size(16)
            box.append(icon)

            label = Gtk.Label(label=title)
            label.set_xalign(0.0)
            box.append(label)

            row.set_child(box)
            self.steps_list.append(row)

        self.update_sidebar_selection()

    def update_sidebar_selection(self):
        for i, row in enumerate(self.steps_list):
            if i == self.current_index:
                row.add_css_class("selected")
            else:
                row.remove_css_class("selected")

    def build_welcome_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup(
            "<span size='large' weight='bold'>Welcome to Printer Setup Wizard (Fake)</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")

        desc = Gtk.Label(
            label=ballmerize(
                "This wizard will help you set up your printer.\n"
                "Or at least pretend to, in a very realistic way."
            )
        )
        desc.set_wrap(True)
        desc.set_xalign(0.0)
        desc.add_css_class("wizard-body")

        info = Gtk.Label(
            label=ballmerize(
                "This is a joke installer. Nothing will be installed.\n"
                "Click Next to continue."
            )
        )
        info.set_wrap(True)
        info.set_xalign(0.0)
        info.add_css_class("wizard-body")

        box.append(title)
        box.append(desc)
        box.append(info)

        self.stack.add_titled(box, "welcome", "Welcome")
        self.page_ids.append("welcome")
        self.page_titles.append("Welcome")

    def build_search_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup(
            "<span size='large' weight='bold'>Searching for Printers…</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        text = Gtk.Label(
            label=ballmerize(
                "The wizard is now searching your network and USB ports for printers.\n"
                "This may take an unnecessarily long time."
            )
        )
        text.set_wrap(True)
        text.set_xalign(0.0)
        text.add_css_class("wizard-body")
        box.append(text)

        self.stack.add_titled(box, "search", "Searching for Printers…")
        self.page_ids.append("search")
        self.page_titles.append("Searching for Printers…")

    def build_install_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup(
            "<span size='large' weight='bold'>Install Printer Drivers</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        text = Gtk.Label(
            label=ballmerize(
                "This page will never be reached in a realistic scenario.\n"
                "The wizard will crash before you get here."
            )
        )
        text.set_wrap(True)
        text.set_xalign(0.0)
        text.add_css_class("wizard-body")
        box.append(text)

        self.stack.add_titled(box, "install", "Install Printer Drivers")
        self.page_ids.append("install")
        self.page_titles.append("Install Printer Drivers")

    def build_finish_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self.finish_title = Gtk.Label()
        self.finish_title.set_markup(
            "<span size='large' weight='bold'>Wizard Completed (Somehow)</span>"
        )
        self.finish_title.set_xalign(0.0)
        self.finish_title.add_css_class("wizard-title")

        self.finish_label = Gtk.Label(
            label=ballmerize(
                "If you see this, something went wrong with the joke.\n"
                "The wizard was supposed to crash earlier."
            )
        )
        self.finish_label.set_wrap(True)
        self.finish_label.set_xalign(0.0)
        self.finish_label.add_css_class("wizard-body")

        box.append(self.finish_title)
        box.append(self.finish_label)

        self.stack.add_titled(box, "finish", "Finish")
        self.page_ids.append("finish")
        self.page_titles.append("Finish")

    def show_page(self, index):
        self.current_index = index
        self.stack.set_visible_child_name(self.page_ids[index])
        self.update_buttons()
        self.update_sidebar_selection()

        if self.page_ids[index] == "search" and not self.crashed:
            GLib.timeout_add(800, self.trigger_crash)

    def update_buttons(self):
        page_id = self.page_ids[self.current_index]

        if page_id == "welcome":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id == "search":
            self.back_button.set_sensitive(True)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id == "install":
            self.back_button.set_sensitive(True)
            self.next_button.set_label("Next")
            self.cancel_button.set_sensitive(True)
        elif page_id == "finish":
            self.back_button.set_sensitive(False)
            self.next_button.set_label("Finish")
            self.next_button.set_sensitive(True)
            self.cancel_button.set_sensitive(False)

    def on_back_clicked(self, button):
        if self.current_index > 0:
            self.show_page(self.current_index - 1)

    def on_next_clicked(self, button):
        page_id = self.page_ids[self.current_index]
        if page_id in ("welcome", "search", "install"):
            self.show_page(self.current_index + 1)
        elif page_id == "finish":
            self.close()

    def on_cancel_clicked(self, button):
        self.close()

    def trigger_crash(self):
        if self.crashed:
            return False
        self.crashed = True

        dialog = Gtk.AlertDialog(
            message=ballmerize("Printer Setup Wizard has encountered an error"),
            detail=ballmerize(
                "An unexpected error occurred and the wizard must close.\n"
                "This is extremely realistic printer behavior."
            ),
            buttons=[ballmerize("Close")],
        )

        def on_done(d, result):
            d.choose_finish(result)
            self.close()

        dialog.choose(self, None, on_done)
        return False


# ---------------------- real installer/uninstaller window ----------------------


class InstallerWindow(Gtk.ApplicationWindow):
    def __init__(self, app, package_name, manager, metadata, mode="install"):
        super().__init__(application=app)
        self.connect("close-request", lambda *a: self.app.quit())
        self.app = app
        self.package_name = package_name
        self.manager = manager
        self.metadata = metadata or {}
        self.mode = mode
        self.install_started = False
        self.install_finished = False

        self.program_name = friendly_name_from_pkg(self.package_name)

        title_action = "Setup" if self.mode == "install" else "Uninstaller"
        self.set_title(f"{self.program_name} {title_action}")
        self.set_default_size(600, -1)
        self.set_resizable(False)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label=f"{self.program_name} {title_action}"))
        self.set_titlebar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(content)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sidebar.set_margin_top(16)
        sidebar.set_margin_bottom(16)
        sidebar.set_margin_start(16)
        sidebar.set_margin_end(0)
        sidebar.add_css_class("sidebar")
        content.append(sidebar)

        icon_image = self.create_program_icon()
        sidebar.append(icon_image)

        steps_label = Gtk.Label(label="Steps")
        steps_label.set_xalign(0.0)
        steps_label.add_css_class("wizard-title")
        sidebar.append(steps_label)

        self.steps_list = Gtk.ListBox()
        self.steps_list.set_selection_mode(Gtk.SelectionMode.NONE)
        sidebar.append(self.steps_list)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.set_margin_top(16)
        self.stack.set_margin_bottom(16)
        self.stack.set_margin_start(0)
        self.stack.set_margin_end(16)
        content.append(self.stack)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(separator)

        button_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_panel.set_margin_top(6)
        button_panel.set_margin_bottom(6)
        button_panel.set_margin_start(12)
        button_panel.set_margin_end(12)
        root.append(button_panel)

        spacer = Gtk.Box()
        button_panel.append(spacer)

        self.back_button = Gtk.Button(label="Back")
        self.next_button = Gtk.Button(label="Next")
        self.cancel_button = Gtk.Button(label="Cancel")

        button_panel.append(self.back_button)
        button_panel.append(self.next_button)
        button_panel.append(self.cancel_button)

        self.back_button.connect("clicked", self.on_back_clicked)
        self.next_button.connect("clicked", self.on_next_clicked)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)

        self.page_ids = []
        self.page_titles = []
        self.current_index = 0

        self.build_pages()
        self.build_sidebar_steps()
        self.show_page(0)
        self.apply_css()

    def create_program_icon(self):
        icon = Gtk.Image()
        icon.set_pixel_size(48)

        icon_theme = Gtk.IconTheme.get_for_display(self.get_display())
        candidates = [
            self.package_name,
            self.program_name.lower().replace(" ", "-"),
            "application-x-executable",
        ]

        for name in candidates:
            if icon_theme.has_icon(name):
                icon.set_from_icon_name(name)
                break
        else:
            icon.set_from_icon_name("application-x-executable")

        return icon

    def apply_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            .wizard-title {
                font-size: 18px;
                font-weight: bold;
            }
            .wizard-body {
                font-size: 14px;
            }
            button {
                padding: 8px 18px;
                font-size: 14px;
            }
            progressbar {
                min-height: 12px;
            }
            textview, textview text {
                font-family: monospace;
                font-size: 14px;
            }
            textview {
                border: 1px solid @borders;
                border-radius: 4px;
                padding: 6px;
            }
            .sidebar {
                border-right: 1px solid @borders;
                padding-right: 12px;
            }
            .step-row.selected {
                background-color: @accent_bg_color;
                color: @accent_fg_color;
            }
        """
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_pages(self):
        self.build_welcome_page()
        self.build_info_page()
        self.build_deps_page()
        self.build_install_page()
        self.build_finish_page()

    def build_sidebar_steps(self):
        self.steps_list.remove_all()
        for idx, title in enumerate(self.page_titles):
            row = Gtk.ListBoxRow()
            row.add_css_class("step-row")
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            box.set_margin_start(4)
            box.set_margin_end(4)

            icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
            icon.set_pixel_size(16)
            box.append(icon)

            label = Gtk.Label(label=title)
            label.set_xalign(0.0)
            box.append(label)

            row.set_child(box)
            self.steps_list.append(row)

        self.update_sidebar_selection()

    def update_sidebar_selection(self):
        for i, row in enumerate(self.steps_list):
            if i == self.current_index:
                row.add_css_class("selected")
            else:
                row.remove_css_class("selected")

    def build_welcome_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        action_word = "Setup Wizard" if self.mode == "install" else "Uninstaller"
        title = Gtk.Label()
        title.set_markup(
            f"<span size='large' weight='bold'>Welcome to the {GLib.markup_escape_text(self.program_name)} {action_word}</span>"
        )
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")

        if self.mode == "install":
            desc_text = (
                self.metadata.get("description")
                or f"Installer for {self.program_name}."
            )
            info_text = (
                "This wizard will guide you through the installation.\n"
                "Click Next to continue or Cancel to exit the Setup."
            )
        else:
            desc_text = f"This wizard will guide you through the uninstallation of {self.program_name}."
            info_text = (
                "You can remove this application from your system.\n"
                "Click Next to continue or Cancel to exit."
            )

        desc = Gtk.Label(label=ballmerize(desc_text))
        desc.set_wrap(True)
        desc.set_xalign(0.0)
        desc.add_css_class("wizard-body")

        info = Gtk.Label(label=ballmerize(info_text))
        info.set_wrap(True)
        info.set_xalign(0.0)
        info.add_css_class("wizard-body")

        box.append(title)
        box.append(desc)
        box.append(info)

        self.stack.add_titled(box, "welcome", "Welcome")
        self.page_ids.append("welcome")
        self.page_titles.append("Welcome")

    def build_info_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>Package Information</span>")
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        grid = Gtk.Grid(column_spacing=12, row_spacing=6)

        def add_row(row, label_text, value):
            lbl = Gtk.Label(label=ballmerize(label_text))
            lbl.set_xalign(0.0)
            val = Gtk.Label(label=ballmerize(value or "Unknown"))
            val.set_xalign(0.0)
            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(val, 1, row, 1, 1)

        add_row(0, "Name:", self.metadata.get("name", self.program_name))
        add_row(1, "Version:", self.metadata.get("version", "Unknown"))
        add_row(2, "Package manager:", self.manager or "Unknown")
        add_row(3, "Homepage:", self.metadata.get("homepage", "Unknown"))

        box.append(grid)
        self.stack.add_titled(box, "info", "Information")
        self.page_ids.append("info")
        self.page_titles.append("Information")

    def build_deps_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>Dependencies</span>")
        title.set_xalign(0.0)
        title.add_css_class("wizard-title")
        box.append(title)

        deps = self.metadata.get("depends", [])
        if self.mode == "uninstall":
            label = Gtk.Label(
                label=ballmerize(
                    "Uninstalling may remove this package, but dependencies might remain if used by other software."
                )
            )
            label.set_xalign(0.0)
            label.set_wrap(True)
            label.add_css_class("wizard-body")
            box.append(label)
        else:
            if deps:
                label = Gtk.Label(
                    label=ballmerize(
                        "The following packages may be installed or required:"
                    )
                )
                label.set_xalign(0.0)
                label.set_wrap(True)
                label.add_css_class("wizard-body")
                box.append(label)

                listbox = Gtk.ListBox()
                listbox.set_selection_mode(Gtk.SelectionMode.NONE)
                for d in deps:
                    row = Gtk.ListBoxRow()
                    row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                    row_box.set_margin_top(2)
                    row_box.set_margin_bottom(2)
                    row_box.set_margin_start(4)
                    row_box.set_margin_end(4)

                    bullet = Gtk.Label(label=ballmerize("•"))
                    bullet.set_xalign(0.0)
                    row_box.append(bullet)

                    dep_label = Gtk.Label(label=ballmerize(d))
                    dep_label.set_xalign(0.0)
                    row_box.append(dep_label)

                    row.set_child(row_box)
                    listbox.append(row)
                box.append(listbox)
            else:
                label = Gtk.Label(
                    label=ballmerize("No dependency information available.")
                )
                label.set_xalign(0.0)
                label.set_wrap(True)
                label.add_css_class("wizard-body")
                box.append(label)

        self.stack.add_titled(box, "deps", "Dependencies")
        self.page_ids.append("deps")
        self.page_titles.append("Dependencies")

    def build_install_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(24)
        outer.set_margin_bottom(24)
        outer.set_margin_start(24)
        outer.set_margin_end(24)

        if self.mode == "install":
            label_text = (
                f"Ready to install {self.program_name}. Click Install to begin."
            )
            button_label = "Install"
        else:
            label_text = (
                f"Ready to uninstall {self.program_name}. Click Uninstall to begin."
            )
            button_label = "Uninstall"

        label = Gtk.Label(label=ballmerize(label_text))
        label.set_xalign(0.0)
        label.add_css_class("wizard-body")

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)

        self.toggle_output_button = Gtk.Button(label=ballmerize("Show details"))
        self.toggle_output_button.connect("clicked", self.on_toggle_output)

        self.output_revealer = Gtk.Revealer()
        self.output_revealer.set_reveal_child(False)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(300)

        self.output_buffer = Gtk.TextBuffer()
        textview = Gtk.TextView(buffer=self.output_buffer)
        textview.set_editable(False)
        textview.set_monospace(True)
        scrolled.set_child(textview)

        self.output_revealer.set_child(scrolled)

        outer.append(label)
        outer.append(self.progress)
        outer.append(self.toggle_output_button)
        outer.append(self.output_revealer)

        self.stack.add_titled(outer, "install", button_label)
        self.page_ids.append("install")
        self.page_titles.append(button_label)

    def build_finish_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self.finish_title = Gtk.Label()
        self.finish_title.set_markup(
            "<span size='large' weight='bold'>Completed</span>"
        )
        self.finish_title.set_xalign(0.0)
        self.finish_title.add_css_class("wizard-title")

        self.finish_label = Gtk.Label(label="")
        self.finish_label.set_wrap(True)
        self.finish_label.set_xalign(0.0)
        self.finish_label.add_css_class("wizard-body")

        box.append(self.finish_title)
        box.append(self.finish_label)

        self.stack.add_titled(box, "finish", "Finish")
        self.page_ids.append("finish")
        self.page_titles.append("Finish")

    def show_page(self, index):
        self.current_index = index
        page_id = self.page_ids[index]
        self.stack.set_visible_child_name(page_id)
        self.update_buttons()
        self.update_sidebar_selection()

    def update_buttons(self):
        page_id = self.page_ids[self.current_index]

        if page_id == "welcome":
            self.back_button.set_sensitive(False)
            self.next_button.set_label(ballmerize("Next"))
            self.cancel_button.set_sensitive(True)

        elif page_id in ("info", "deps"):
            self.back_button.set_sensitive(True)
            self.next_button.set_label(ballmerize("Next"))
            self.next_button.set_sensitive(True)
            self.cancel_button.set_sensitive(True)

        elif page_id == "install":
            self.back_button.set_sensitive(not self.install_started)
            if not self.install_started:
                self.next_button.set_label(
                    ballmerize("Install" if self.mode == "install" else "Uninstall")
                )
                self.next_button.set_sensitive(True)
            else:
                self.next_button.set_label(ballmerize("Working..."))
                self.next_button.set_sensitive(False)
            self.cancel_button.set_sensitive(not self.install_started)

        elif page_id == "finish":
            self.back_button.set_sensitive(False)
            self.next_button.set_label(ballmerize("Finish"))
            self.next_button.set_sensitive(True)
            self.cancel_button.set_sensitive(False)

    def on_back_clicked(self, button):
        if self.current_index > 0:
            self.show_page(self.current_index - 1)

    def on_next_clicked(self, button):
        page_id = self.page_ids[self.current_index]

        if page_id in ("welcome", "info", "deps"):
            self.show_page(self.current_index + 1)
        elif page_id == "install":
            if not self.install_started:
                self.start_install()
        elif page_id == "finish":
            self.close()

    def on_cancel_clicked(self, button):
        self.close()

    def on_toggle_output(self, button):
        revealed = self.output_revealer.get_reveal_child()
        self.output_revealer.set_reveal_child(not revealed)
        button.set_label(ballmerize("Hide details" if not revealed else "Show details"))

    def append_output(self, text):
        text = ballmerize(text)
        end = self.output_buffer.get_end_iter()
        self.output_buffer.insert(end, text)

    def start_pulse_animation(self):
        self.progress.set_pulse_step(0.05)

        def pulse():
            if not self.install_started or self.install_finished:
                return False
            self.progress.pulse()
            return True

        GLib.timeout_add(100, pulse)

    def animate_status_text(self):
        dots = ["", ".", "..", "..."]
        index = 0
        base = "Installing" if self.mode == "install" else "Uninstalling"

        def update():
            nonlocal index
            if self.install_finished:
                return False
            self.progress.set_text(ballmerize(f"{base}{dots[index]}"))
            index = (index + 1) % len(dots)
            return True

        GLib.timeout_add(500, update)

    def start_install(self):
        self.install_started = True
        self.update_buttons()

        action_word = "installation" if self.mode == "install" else "uninstallation"
        self.append_output(
            ballmerize(
                f"Starting {action_word} of {self.program_name} using {self.manager}...\n"
            )
        )
        self.progress.set_text(ballmerize("Working"))
        self.start_pulse_animation()
        self.animate_status_text()

        def worker():
            ret = self.run_command()
            GLib.idle_add(self.install_done, ret)

        threading.Thread(target=worker, daemon=True).start()

    def run_command(self):
        if not self.manager:
            GLib.idle_add(
                self.append_output, ballmerize("No supported package manager found.\n")
            )
            return 1

        if self.mode == "install":
            upgrade = self.metadata.get("upgrade", False)
            reinstall = self.metadata.get("reinstall", False)

            if self.manager == "apt":
                if upgrade:
                    cmd = [
                        "sudo",
                        "-S",
                        "apt",
                        "install",
                        "--only-upgrade",
                        "-y",
                        self.package_name,
                    ]
                elif reinstall:
                    cmd = [
                        "sudo",
                        "-S",
                        "apt",
                        "install",
                        "--reinstall",
                        "-y",
                        self.package_name,
                    ]
                else:
                    cmd = ["sudo", "-S", "apt", "install", "-y", self.package_name]
            elif self.manager == "dnf":
                if upgrade:
                    cmd = ["sudo", "-S", "dnf", "upgrade", "-y", self.package_name]
                elif reinstall:
                    cmd = ["sudo", "-S", "dnf", "reinstall", "-y", self.package_name]
                else:
                    cmd = ["sudo", "-S", "dnf", "install", "-y", self.package_name]
            elif self.manager == "pacman":
                if upgrade:
                    cmd = [
                        "sudo",
                        "-S",
                        "pacman",
                        "-Syu",
                        "--noconfirm",
                        self.package_name,
                    ]
                else:
                    cmd = ["sudo", "-S", "pacman", "--noconfirm", self.package_name]
            else:
                GLib.idle_add(
                    self.append_output, ballmerize("Unsupported package manager.\n")
                )
                return 1
        else:
            if self.manager == "apt":
                cmd = ["sudo", "-S", "apt", "remove", "-y", self.package_name]
            elif self.manager == "dnf":
                cmd = ["sudo", "-S", "dnf", "remove", "-y", self.package_name]
            elif self.manager == "pacman":
                cmd = ["sudo", "-S", "pacman", "-R", "--noconfirm", self.package_name]
            else:
                GLib.idle_add(
                    self.append_output, ballmerize("Unsupported package manager.\n")
                )
                return 1

        # --- GTK4 sudo password dialog (thread-safe) ---
        password_event = threading.Event()
        password_value = {"pw": None}

        def show_password_dialog():
            dialog = Gtk.Window(
                title="Authentication Required",
                transient_for=self.app.main_window,
                modal=True,
            )
            dialog.set_resizable(False)
            dialog.set_default_size(360, -1)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.set_margin_top(16)
            box.set_margin_bottom(16)
            box.set_margin_start(16)
            box.set_margin_end(16)
            dialog.set_child(box)
            box.set_margin_top(16)
            box.set_margin_bottom(16)
            box.set_margin_start(16)
            box.set_margin_end(16)
            box.set_spacing(12)

            label = Gtk.Label(
                label=ballmerize(
                    "Installing or removing software requires elevated privileges.\n\n"
                    "On Linux, the root user is the equivalent of Windows' TrustedInstaller.\n\n"
                    "These permissions are required to continue."
                )
            )
            label.set_wrap(True)
            label.set_xalign(0.0)
            box.append(label)

            entry = Gtk.Entry()
            entry.set_visibility(False)
            entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
            entry.set_placeholder_text("Password")
            box.append(entry)

            button_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=6,
            )
            button_box.set_halign(Gtk.Align.END)
            button_box.set_margin_top(12)
            box.append(button_box)

            cancel_btn = Gtk.Button(label="Cancel")
            auth_btn = Gtk.Button(label="Authenticate")
            button_box.append(cancel_btn)
            button_box.append(auth_btn)

            def do_cancel(_btn):
                dialog.destroy()
                password_event.set()

            def do_auth(_btn):
                password_value["pw"] = entry.get_text()
                dialog.destroy()
                password_event.set()

            cancel_btn.connect("clicked", do_cancel)
            auth_btn.connect("clicked", do_auth)

            # ENTER key submits the dialog
            entry.connect("activate", lambda *_: do_auth(None))

            dialog.present()

        GLib.idle_add(show_password_dialog)
        password_event.wait()
        password = password_value["pw"]
        if not password:
            return 1
        # --- end sudo password dialog ---

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            GLib.idle_add(
                self.append_output, ballmerize(f"Failed to start command: {e}\n")
            )
            return 1

        try:
            proc.stdin.write(password + "\n")
            proc.stdin.flush()
        except Exception as e:
            GLib.idle_add(
                self.append_output, ballmerize(f"Failed to send password: {e}\n")
            )

        try:
            for line in proc.stdout:
                GLib.idle_add(self.append_output, line)
        except Exception as e:
            GLib.idle_add(
                self.append_output, ballmerize(f"Error reading command output: {e}\n")
            )
            return 1

        return proc.wait()

    def install_done(self, retcode):
        self.install_finished = True
        if retcode == 0:
            self.progress.set_fraction(1.0)
            self.progress.set_text(ballmerize("Completed"))
            if self.mode == "install":
                self.append_output(ballmerize("Installation finished successfully.\n"))
                self.finish_title.set_markup(
                    ballmerize(
                        "<span size='large' weight='bold'>Setup Completed</span>"
                    )
                )
                self.finish_label.set_text(
                    ballmerize(f"{self.program_name} has been installed.")
                )
            else:
                self.append_output(
                    ballmerize("Uninstallation finished successfully.\n")
                )
                self.finish_title.set_markup(
                    ballmerize(
                        "<span size='large' weight='bold'>Uninstall Completed</span>"
                    )
                )
                self.finish_label.set_text(
                    ballmerize(f"{self.program_name} has been removed.")
                )
        else:
            self.progress.set_fraction(0.0)
            self.progress.set_text(ballmerize("Failed"))
            if self.mode == "install":
                self.append_output(ballmerize("Installation failed.\n"))
                self.finish_title.set_markup(
                    ballmerize("<span size='large' weight='bold'>Setup Failed</span>")
                )
                self.finish_label.set_text(
                    ballmerize(
                        f"An error occurred while installing {self.program_name}."
                    )
                )
            else:
                self.append_output(ballmerize("Uninstallation failed.\n"))
                self.finish_title.set_markup(
                    ballmerize(
                        "<span size='large' weight='bold'>Uninstall Failed</span>"
                    )
                )
                self.finish_label.set_text(
                    ballmerize(
                        f"An error occurred while uninstalling {self.program_name}."
                    )
                )

        self.show_page(self.page_ids.index("finish"))


# ---------------------- application ----------------------


class InstallerApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.example.DynamicWin32Installer",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.main_window = None

    def do_activate(self):
        win = Gtk.ApplicationWindow(application=self)
        win.set_default_size(1, 1)
        win.set_opacity(0)
        win.present()
        self.main_window = win

        if STEVE_BALLMER_MODE:
            warning_text = (
                "You launched this program with --steve-ballmer.\n\n"
                "When this mode is active, every word shown in installer logs and messages "
                'and nearly every word in the UI will be replaced with the single word: "developers".\n\n'
                "Press OK to continue with this mode enabled, or close this dialog to exit the program."
            )
            dialog = Gtk.AlertDialog(
                message=ballmerize("Steve Ballmer Mode Enabled", skip=True),
                detail=ballmerize(warning_text, skip=True),
                buttons=[ballmerize("Cancel", skip=True), ballmerize("OK", skip=True)],
            )

            def on_done(d, result):
                idx = d.choose_finish(result)
                if idx == 1:
                    sel = PackageSelectionDialog(self.main_window)
                    sel.connect("response", self.on_dialog_response)
                    sel.present()
                else:
                    self.quit()

            dialog.choose(self.main_window, None, on_done)
            return

        dialog = PackageSelectionDialog(self.main_window)
        dialog.connect("response", self.on_dialog_response)
        dialog.present()

    def show_error_dialog(self, message, secondary=None, quit_after=False):
        dialog = Gtk.AlertDialog(
            message=ballmerize(message),
            detail=ballmerize(secondary or ""),
            buttons=[ballmerize("OK")],
        )

        def on_done(d, result):
            d.choose_finish(result)
            if quit_after:
                self.quit()

        dialog.choose(self.main_window, None, on_done)

    def show_info_dialog(self, message, secondary=None, quit_after=False):
        dialog = Gtk.AlertDialog(
            message=ballmerize(message),
            detail=ballmerize(secondary or ""),
            buttons=[ballmerize("OK")],
        )

        def on_done(d, result):
            d.choose_finish(result)
            if quit_after:
                self.quit()

        dialog.choose(self.main_window, None, on_done)

    def ask_upgrade(self, pkg, manager, metadata):
        dialog = Gtk.AlertDialog(
            message=ballmerize(f"{pkg} is already installed."),
            detail=ballmerize("Do you want to upgrade or reinstall it?"),
            buttons=[
                ballmerize("Cancel"),
                ballmerize("Reinstall"),
                ballmerize("Upgrade"),
            ],
        )

        def on_done(d, result):
            idx = d.choose_finish(result)
            if idx == 2:
                metadata["upgrade"] = True
            elif idx == 1:
                metadata["reinstall"] = True
            else:
                self.quit()
                return
            installer = InstallerWindow(self, pkg, manager, metadata, mode="install")
            installer.present()

        dialog.choose(self.main_window, None, on_done)

    def on_dialog_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            pkg = dialog.get_package_name()
            mode = dialog.get_mode()
            dialog.destroy()
            if not pkg:
                self.show_error_dialog("No package name entered.", quit_after=True)
                return

            if is_windows_malware_phrase(pkg):
                joke = JokeInstallerWindow(self)
                joke.present()
                return

            if is_sandisk_assistant(pkg):
                sandisk = SandiskJokeInstallerWindow(self)
                sandisk.present()
                return

            if is_wd_assistant(pkg):
                wd = WDJokeInstallerWindow(self)
                wd.present()
                return

            if is_seagate_dashboard(pkg):
                seagate = SeagateDashboardJokeInstallerWindow(self)
                seagate.present()
                return

            if is_rgb_mouse_installer(pkg):
                rgb = RGBMouseJokeInstallerWindow(self)
                rgb.present()
                return

            if is_printer_setup_wizard(pkg):
                printer = PrinterSetupJokeInstallerWindow(self)
                printer.present()
                return

            if is_windows_promotional(pkg):
                title, body = random_windows_promo()
                self.show_info_dialog(title, body, quit_after=True)
                return

            manager = detect_package_manager()
            if not manager:
                self.show_error_dialog(
                    "No supported package manager found.", quit_after=True
                )
                return

            metadata = get_package_metadata(manager, pkg)
            if metadata is None:
                self.show_error_dialog(
                    "Could not retrieve package metadata.",
                    f"Package '{pkg}' may not exist in the repositories.",
                    quit_after=True,
                )
                return

            installed = is_installed(manager, pkg)

            if mode == "install":
                if installed:
                    self.ask_upgrade(pkg, manager, metadata)
                else:
                    installer = InstallerWindow(
                        self, pkg, manager, metadata, mode="install"
                    )
                    installer.present()
            else:
                if not installed:
                    self.show_error_dialog(
                        "Package is not installed.",
                        f"'{pkg}' does not appear to be installed.",
                        quit_after=True,
                    )
                    return
                installer = InstallerWindow(
                    self, pkg, manager, metadata, mode="uninstall"
                )
                installer.present()
        else:
            dialog.destroy()
            self.quit()


def main():
    app = InstallerApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    main()