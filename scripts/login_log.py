#!/usr/bin/python3
"""Password-protected client for the local Login History service."""

import argparse
import ctypes
import getpass
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

SOCKET = "/run/i3-login-log.sock"
ADMIN = "/usr/local/libexec/i3-login-log/admin.py"
RETENTION = 7 * 24 * 60 * 60
MAX_RESPONSE = 4 * 1024 * 1024


class Client:
    def __init__(self, timeout=30):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(timeout)
        try:
            self.socket.connect(SOCKET)
        except OSError:
            self.socket.close()
            raise RuntimeError("Login History unavailable; run setup.sh apply --configs-only") from None
        self.stream = self.socket.makefile("rwb")
        self.last_request = time.monotonic()

    def request(self, op, **fields):
        encoded = json.dumps({"op": op, **fields}, ensure_ascii=False).encode() + b"\n"
        if len(encoded) > 8192:
            raise ValueError("Request too large")
        self.stream.write(encoded)
        self.stream.flush()
        line = self.stream.readline(MAX_RESPONSE + 1)
        if not line.endswith(b"\n") or len(line) > MAX_RESPONSE:
            raise RuntimeError("Service disconnected; close and reopen Login History")
        response = json.loads(line)
        if not isinstance(response, dict) or type(response.get("ok")) is not bool:
            raise RuntimeError("Invalid service response")
        if not response["ok"]:
            raise ValueError(response.get("error", "Login History request failed"))
        self.last_request = time.monotonic()
        return response["result"]

    def entries(self, date="", search="", event_type="", result=""):
        rows, before = [], 0
        while True:
            page = self.request("list", date=date, search=search, before=before, event_type=event_type, result=result)
            rows.extend(page["rows"])
            following = page["next"]
            if not following:
                return sorted(rows, key=lambda row: (row["created_at"], row["id"]), reverse=True)
            if following >= before > 0 or len(rows) > 10000:
                raise RuntimeError("History query too large; use a date filter")
            before = following

    def close(self):
        self.stream.close()
        self.socket.close()


def status():
    client = Client(timeout=.5)
    try:
        return client.request("status")
    finally:
        client.close()


def gtk():
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    return Gtk


def secret_form(title, description, fields, parent=None, recovery=False):
    Gtk = gtk()
    dialog = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
    if recovery:
        dialog.add_button("Forgot password", 100)
    dialog.add_button("Continue", Gtk.ResponseType.ACCEPT)
    dialog.set_default_response(Gtk.ResponseType.ACCEPT)
    box = dialog.get_content_area()
    box.set_border_width(16)
    box.set_spacing(10)
    box.add(Gtk.Label(label=description, wrap=True, max_width_chars=60, xalign=0))
    entries = []
    for caption in fields:
        entry = Gtk.Entry(visibility=False, activates_default=True)
        label = Gtk.Label(label=caption, xalign=0)
        label.set_mnemonic_widget(entry)
        box.add(label)
        box.add(entry)
        entries.append(entry)
    dialog.show_all()
    try:
        response = dialog.run()
        if response == 100:
            return "recover"
        return [entry.get_text() for entry in entries] if response == Gtk.ResponseType.ACCEPT else None
    finally:
        for entry in entries:
            entry.set_text("")
        dialog.destroy()


def message(text, parent=None):
    Gtk = gtk()
    dialog = Gtk.MessageDialog(transient_for=parent, modal=True, message_type=Gtk.MessageType.INFO,
                               buttons=Gtk.ButtonsType.CLOSE, text=text)
    dialog.run()
    dialog.destroy()


def confirm_action(parent, title, detail):
    Gtk = gtk()
    dialog = Gtk.MessageDialog(transient_for=parent, modal=True, message_type=Gtk.MessageType.QUESTION,
                               text=title)
    dialog.format_secondary_text(detail)
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
    dialog.add_button("Continue", Gtk.ResponseType.ACCEPT)
    dialog.set_default_response(Gtk.ResponseType.CANCEL)
    response = dialog.run()
    dialog.destroy()
    return response == Gtk.ResponseType.ACCEPT


def show_code(code, parent=None):
    Gtk = gtk()
    dialog = Gtk.Dialog(title="Save your recovery code", transient_for=parent, modal=True)
    dialog.add_button("I saved it off this laptop", Gtk.ResponseType.ACCEPT)
    content = dialog.get_content_area()
    content.set_border_width(20)
    content.set_spacing(16)
    content.add(Gtk.Label(label="Write this code down or save it on another device.\n"
                               "It can reset access without deleting your history.\n"
                               "The previous recovery code no longer works."))
    label = Gtk.Label(label=code, selectable=False)
    label.set_line_wrap(True)
    content.add(label)
    content.add(Gtk.Label(label="Lost this display? Unlock Login History, then choose New recovery code."))
    dialog.show_all()
    try:
        dialog.run()
    finally:
        label.set_text("")
        dialog.destroy()


def checked_password(values):
    if not values[0]:
        raise ValueError("Password cannot be empty")
    if values[0] != values[1]:
        raise ValueError("Passwords do not match")
    return values[0]


def enroll(migration):
    fields = ["New application password", "Confirm application password"]
    if migration:
        fields.append("Previous vault password (to preserve existing history)")
    values = secret_form("Set up Login History", "Administrator authorization protects initial setup.\n"
                         "Tracking starts Off. Save the recovery code off this laptop.", fields)
    if values is None:
        return False
    try:
        password = checked_password(values)
        request = json.dumps({"password": password, "old_password": values[2] if migration else ""})
        result = subprocess.run(["/usr/bin/pkexec", ADMIN], input=request, text=True,
                                capture_output=True, timeout=180)
        if result.returncode:
            raise RuntimeError("Administrator authorization or enrollment failed; existing history was preserved")
        response = json.loads(result.stdout)
        if not response.get("ok"):
            raise ValueError(response.get("error", "Enrollment failed; existing history was preserved"))
        show_code(response["result"]["code"])
        if response.get("cleanup_pending"):
            message("Protected history is ready. Some old files changed during setup and were preserved.\n"
                    "Administrator cleanup is still needed; those old copies have the previous protection.")
        return True
    finally:
        values.clear()
        password = request = ""


def recover(client):
    values = secret_form("Recover Login History", "Enter your off-laptop recovery code.\n"
                          "Recovery preserves history and the current tracking state.",
                          ["New application password", "Confirm new password", "Recovery code"])
    if values is None:
        return False
    try:
        password = checked_password(values)
        show_code(client.request("recover", code=values[2], password=password)["code"])
        return True
    finally:
        values.clear()
        password = ""


def authenticate(client):
    current = client.request("status")
    if current["setup"] and not enroll(current["migration"]):
        return False
    while True:
        values = secret_form("Unlock Login History", "Enter your application password.",
                             ["Application password"], recovery=True)
        if values is None:
            return False
        try:
            if values == "recover":
                recover(client)
            else:
                client.request("auth", password=values[0])
                return True
        except (ValueError, RuntimeError) as error:
            message(str(error))
        finally:
            if isinstance(values, list):
                values.clear()


def toggle():
    client = Client()
    try:
        if authenticate(client):
            current = client.request("status")
            enabled = client.request("set_enabled", enabled=not current["enabled"])["enabled"]
            message("Login tracking is On. New i3 logins will be recorded." if enabled else
                    "Login tracking is Off. Existing history still expires after seven days.")
    finally:
        client.close()

def view(date="", search="", event_type="", result=""):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GdkPixbuf, GLib, Gtk

    client = Client()
    if not authenticate(client):
        client.close()
        return

    window = Gtk.Window(title="Login history")
    window.set_default_size(1050, 700)
    window.connect("destroy", Gtk.main_quit)
    layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
    window.add(layout)
    filters = Gtk.Box(spacing=8)
    date_input = Gtk.Entry(placeholder_text="Date: YYYY-MM-DD (all dates if empty)", text=date)
    date_input.set_width_chars(32)
    date_label = Gtk.Label(label="_Date:", use_underline=True)
    date_label.set_mnemonic_widget(date_input)
    filters.pack_start(date_label, False, False, 0)
    search_input = Gtk.SearchEntry(placeholder_text="Search account, network, session…", text=search)
    refresh = Gtk.Button(label="Refresh")
    rotate = Gtk.Button(label="New recovery code")
    delete = Gtk.Button(label="Delete selected")
    delete.set_sensitive(False)
    for widget in (date_input, search_input, refresh, delete, rotate):
        filters.pack_start(widget, widget is search_input, widget is search_input, 0)
    layout.pack_start(filters, False, False, 0)
    event_filters = Gtk.Box(spacing=8)
    kind_input = Gtk.ComboBoxText()
    result_input = Gtk.ComboBoxText()
    for value, label in (("", "All events"), ("login", "Login"), ("unlock", "Unlock")):
        kind_input.append(value, label)
    for value, label in (("", "All results"), ("success", "Success"), ("failure", "Failed")):
        result_input.append(value, label)
    kind_input.set_active_id(event_type)
    result_input.set_active_id(result)
    for label, widget in (("Event:", kind_input), ("Result:", result_input)):
        event_filters.pack_start(Gtk.Label(label=label), False, False, 0)
        event_filters.pack_start(widget, False, False, 0)
    show_all = Gtk.CheckButton(label="Show all photos")
    event_filters.pack_start(show_all, False, False, 0)
    password_change = Gtk.Button(label="Change password")
    event_filters.pack_end(password_change, False, False, 0)
    layout.pack_start(event_filters, False, False, 0)
    status = Gtk.Label(xalign=0)
    layout.pack_start(status, False, False, 0)
    panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
    layout.pack_start(panes, True, True, 0)
    store = Gtk.TreeStore(str, str, int, str, str)
    tree = Gtk.TreeView(model=store)
    for column, title in enumerate(("Local date / time", "Account")):
        tree.append_column(Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=column))
    tree.append_column(Gtk.TreeViewColumn("Event", Gtk.CellRendererText(), text=3))
    tree.append_column(Gtk.TreeViewColumn("Result", Gtk.CellRendererText(), text=4))
    scroll = Gtk.ScrolledWindow()
    scroll.set_size_request(350, -1)
    scroll.add(tree)
    panes.pack1(scroll, resize=False, shrink=False)
    detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    image = Gtk.Image()
    detail.pack_start(image, False, False, 0)
    photo_label = Gtk.Label()
    detail.pack_start(photo_label, False, False, 0)
    photo_toggle = Gtk.ToggleButton(label="Show photo", sensitive=False)
    detail.pack_start(photo_toggle, False, False, 0)
    text = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
    detail_scroll = Gtk.ScrolledWindow()
    detail_scroll.add(text)
    detail.pack_start(detail_scroll, True, True, 0)
    panes.pack2(detail, resize=True, shrink=False)
    records = {}
    photo_row = None

    def render_photo(*_):
        image.clear()
        photo_label.set_text("")
        photo_toggle.set_label("Hide photo" if photo_toggle.get_active() else "Show photo")
        photo_toggle.set_sensitive(False)
        if photo_row is None:
            return
        if photo_row["created_at"] <= time.time() - RETENTION or not photo_row["photo"]:
            image.set_from_icon_name("image-missing-symbolic", Gtk.IconSize.DIALOG)
            photo_label.set_text("Photo expired" if photo_row["photo"] else "No photo captured")
            return
        photo_toggle.set_sensitive(True)
        if not photo_toggle.get_active():
            image.set_from_icon_name("view-conceal-symbolic", Gtk.IconSize.DIALOG)
            photo_label.set_text("Photo hidden")
            return
        try:
            loader = GdkPixbuf.PixbufLoader.new_with_type("jpeg")
            loader.write(bytes.fromhex(photo_row["photo"]))
            loader.close()
            image.set_from_pixbuf(loader.get_pixbuf())
        except (GLib.Error, ValueError):
            image.set_from_icon_name("image-missing-symbolic", Gtk.IconSize.DIALOG)
            photo_label.set_text("Photo unavailable")

    def selected(selection):
        nonlocal photo_row
        photo_row = None
        photo_toggle.set_active(False)
        render_photo()
        text.get_buffer().set_text("")
        model, item = selection.get_selected()
        row = records.get(model[item][2]) if item else None
        delete.set_sensitive(row is not None)
        if not row:
            return
        try:
            row = client.request("get", id=row["id"])
        except (OSError, ValueError, RuntimeError) as error:
            status.set_text(str(error))
            return
        details = json.loads(row["metadata"])
        details["photo_status"] = row["photo_error"] or "captured"
        text.get_buffer().set_text(json.dumps(details, indent=2, ensure_ascii=False))
        photo_row = row
        render_photo()
        photo_toggle.set_active(show_all.get_active() and photo_toggle.get_sensitive())

    def reload(*_):
        nonlocal photo_row
        photo_row = None
        photo_toggle.set_active(False)
        render_photo()
        delete.set_sensitive(False)
        text.get_buffer().set_text("")
        store.clear()
        records.clear()
        try:
            rows = client.entries(date_input.get_text().strip(), search_input.get_text(),
                                  kind_input.get_active_id(), result_input.get_active_id())
            groups = {}
            for row in rows:
                day = row["local_time"][:10]
                if day not in groups:
                    groups[day] = store.append(None, [day, "", 0, "", ""])
                data = json.loads(row["metadata"])
                store.append(groups[day], [row["local_time"][11:], data["account"], row["id"],
                                          row["event_type"].title(), "Failed" if row["result"] == "failure" else "Success"])
                records[row["id"]] = row
            tree.expand_all()
            count = f"{len(rows)} record" + ("" if len(rows) == 1 else "s")
            monitor = client.request("status").get("failure_monitor", False)
            status.set_text(f"{count} · Last 7 days" + ("" if monitor else " · Failure monitor unavailable"))
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
            status.set_text(str(error))

    def delete_selected(_):
        model, item = tree.get_selection().get_selected()
        row = records.get(model[item][2]) if item else None
        if row is None:
            return
        dialog = Gtk.MessageDialog(transient_for=window, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   text="Delete this login record?")
        dialog.format_secondary_text(f"{row['local_time']}\nThis permanently deletes the record and its photo.")
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Delete", Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.ACCEPT:
            try:
                client.request("delete", id=row['id'])
                reload()
            except (RuntimeError, OSError, subprocess.SubprocessError) as error:
                status.set_text(str(error))

    def replace_password(_):
        values = secret_form("Change password", "Enter your current password and choose a new one.\n"
                             "History, tracking state and your recovery code will stay unchanged.",
                             ["Current password", "New password", "Confirm new password"], parent=window)
        if values is None:
            return
        try:
            password = checked_password(values[1:])
            client.request("change_password", current_password=values[0], password=password)
            status.set_text("Password changed. Your existing recovery code still works.")
        except (OSError, ValueError, RuntimeError) as error:
            status.set_text(str(error))
        finally:
            values.clear()
            password = ""

    def replace_code(_):
        if confirm_action(window, "Replace your recovery code?", "The previous recovery code will stop working. Save the new code off this laptop."):
            try:
                show_code(client.request("rotate_code")["code"], window)
            except (OSError, ValueError, RuntimeError) as error:
                status.set_text(str(error))

    rotate.connect("clicked", replace_code)
    password_change.connect("clicked", replace_password)
    photo_toggle.connect("toggled", render_photo)
    show_all.connect("toggled", lambda button: photo_toggle.set_active(button.get_active() and photo_toggle.get_sensitive()))
    tree.get_selection().connect("changed", selected)
    refresh.connect("clicked", reload)
    delete.connect("clicked", delete_selected)
    date_input.connect("activate", reload)
    search_input.connect("activate", reload)
    kind_input.connect("changed", reload)
    result_input.connect("changed", reload)
    reload()
    window.show_all()
    def expire():
        if time.monotonic() - client.last_request >= 300:
            window.destroy()
            return False
        return True
    timer = GLib.timeout_add_seconds(1, expire)
    try:
        Gtk.main()
    finally:
        if GLib.MainContext.default().find_source_by_id(timer):
            GLib.source_remove(timer)
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("login", "unlock", "status", "toggle", "list", "view", "recover"))
    parser.add_argument("--date", default="")
    parser.add_argument("--search", default="")
    parser.add_argument("--event", choices=("", "login", "unlock"), default="", help="filter event type")
    parser.add_argument("--result", choices=("", "success", "failure"), default="", help="filter authentication result")
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(status()))
        return
    if ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) != 0:
        raise RuntimeError("Could not protect process memory")
    if args.command == "toggle":
        toggle()
    elif args.command == "view":
        view(args.date, args.search, args.event, args.result)
    else:
        client = Client()
        try:
            if args.command in ("login", "unlock"):
                client.request("capture" if args.command == "login" else "unlock")
            elif args.command == "recover":
                recover(client)
            else:
                password = getpass.getpass("Login History password: ")
                try:
                    client.request("auth", password=password)
                finally:
                    password = ""
                print(json.dumps(client.entries(args.date, args.search, args.event, args.result), indent=2, ensure_ascii=False))
        finally:
            client.close()


if __name__ == "__main__":
    trusted = Path("/usr/local/libexec/i3-login-log/client.py")
    if trusted.is_file() and Path(__file__).resolve() != trusted:
        os.execv("/usr/bin/python3", ["/usr/bin/python3", str(trusted), *sys.argv[1:]])
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        if any(command in sys.argv for command in ("view", "toggle", "recover")):
            message(str(error))
        else:
            print(f"Login History: {error}", file=sys.stderr)
        sys.exit(1)
