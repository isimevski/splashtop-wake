#!/usr/bin/python3
"""Wake the current GNOME Wayland desktop and report readiness for Splashtop."""
from __future__ import annotations

import argparse
import os
import sys
import time

SYSTEM_PYTHON = "/usr/bin/python3"

try:
    import gi
except ModuleNotFoundError as error:
    if error.name != "gi":
        raise
    is_virtual_environment = sys.prefix != sys.base_prefix
    is_system_python = os.path.realpath(sys.executable) == os.path.realpath(SYSTEM_PYTHON)
    if is_virtual_environment or not is_system_python:
        os.execv(SYSTEM_PYTHON, [SYSTEM_PYTHON, os.path.abspath(__file__), *sys.argv[1:]])
    print("PyGObject is unavailable. Install Ubuntu's python3-gi package and try again.", file=sys.stderr)
    raise SystemExit(3)

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

REMOTE_INTERFACE = "org.gnome.Mutter.RemoteDesktop"
DISPLAY_INTERFACE = "org.gnome.Mutter.DisplayConfig"
SCREEN_SAVER_INTERFACE = "org.gnome.ScreenSaver"
PROPERTIES = "org.freedesktop.DBus.Properties"
CALL_TIMEOUT_MILLISECONDS = 5_000
DEFAULT_WAIT_SECONDS = 8.0
MAXIMUM_WAIT_SECONDS = 60.0
POLL_SECONDS = 0.5
KEY_LEFT_SHIFT = 42
DISPLAY_POWER_ON = 0
Endpoint = tuple[str, str, str]


class GnomeDesktop:
    def __init__(self) -> None:
        os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def wake(self) -> None:
        self._shift()
        endpoint = (DISPLAY_INTERFACE, "/org/gnome/Mutter/DisplayConfig", PROPERTIES)
        arguments = GLib.Variant("(ssv)", (DISPLAY_INTERFACE, "PowerSaveMode", GLib.Variant("i", DISPLAY_POWER_ON)))
        self._call(endpoint, "Set", arguments)

    def displays(self) -> tuple[int, int]:
        endpoint = (DISPLAY_INTERFACE, "/org/gnome/Mutter/DisplayConfig", DISPLAY_INTERFACE)
        state = self._call(endpoint, "GetCurrentState").unpack()
        return len(state[1]), len(state[2])

    def display_power(self) -> int:
        endpoint = (DISPLAY_INTERFACE, "/org/gnome/Mutter/DisplayConfig", PROPERTIES)
        arguments = GLib.Variant("(ss)", (DISPLAY_INTERFACE, "PowerSaveMode"))
        return self._call(endpoint, "Get", arguments).unpack()[0]

    def is_awake(self) -> bool:
        monitors, active = self.displays()
        return self.display_power() == DISPLAY_POWER_ON and monitors > 0 and active > 0

    def is_locked(self) -> bool:
        endpoint = (SCREEN_SAVER_INTERFACE, "/org/gnome/ScreenSaver", SCREEN_SAVER_INTERFACE)
        return self._call(endpoint, "GetActive").unpack()[0]

    def _shift(self) -> None:
        endpoint = (REMOTE_INTERFACE, "/org/gnome/Mutter/RemoteDesktop", REMOTE_INTERFACE)
        path = self._call(endpoint, "CreateSession").unpack()[0]
        session = (REMOTE_INTERFACE, path, REMOTE_INTERFACE + ".Session")
        try:
            self._call(session, "Start")
            try:
                self._key(session, True)
            finally:
                self._key(session, False)
        finally:
            self._call(session, "Stop")

    def _key(self, session: Endpoint, is_pressed: bool) -> None:
        self._call(session, "NotifyKeyboardKeycode", GLib.Variant("(ub)", (KEY_LEFT_SHIFT, is_pressed)))

    def _call(self, endpoint: Endpoint, method: str, arguments: GLib.Variant | None = None) -> GLib.Variant:
        destination, path, interface = endpoint
        return self.connection.call_sync(destination, path, interface, method, arguments, None,
                                         Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MILLISECONDS, None)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-seconds", type=float, default=DEFAULT_WAIT_SECONDS,
                        help="Seconds to wait for an active display (default: 8, maximum: 60)")
    parser.add_argument("--quiet-if-awake", action="store_true", help="Exit silently when the display is already awake")
    options = parser.parse_args()
    if not 0 <= options.wait_seconds <= MAXIMUM_WAIT_SECONDS:
        parser.error("--wait-seconds must be between 0 and 60")
    return options


def await_display(desktop: GnomeDesktop, wait_seconds: float) -> int:
    deadline = time.monotonic() + wait_seconds
    while True:
        monitors, active = desktop.displays()
        if monitors and active:
            if desktop.is_locked():
                print("Display is awake, but the desktop is locked. Unlock it before connecting.")
                return 2
            print(f"Ready to connect in Splashtop: {active} active display(s), desktop unlocked.")
            return 0
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print("No active display detected. Turn on/reconnect the monitor or attach a display dummy plug.")
            return 1
        time.sleep(min(POLL_SECONDS, remaining))


def wake_if_needed(desktop: GnomeDesktop, options: argparse.Namespace) -> int:
    if desktop.is_awake():
        if options.quiet_if_awake:
            return 0
        print("Display already awake; no wake input sent.")
    else:
        desktop.wake()
        print("Sent native Wayland Shift press/release and enabled display power.")
    return await_display(desktop, options.wait_seconds)


def main() -> int:
    options = arguments()
    try:
        return wake_if_needed(GnomeDesktop(), options)
    except GLib.Error as error:
        print(f"Could not wake the GNOME desktop: {error.message}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
