# Splashtop desktop wake

Repeat the wake procedure verified on this Ubuntu 26.04 GNOME Wayland machine:

1. Check display power and monitor availability; skip wake input if already awake.
2. Open a temporary Mutter remote-input session when waking is necessary.
3. Press and release the left Shift key through native Wayland input.
4. Close the temporary input session and set display power to On.
5. Wait for an active display, check the lock state, and report when to connect.

Run as the logged-in desktop user, including from an SSH terminal for that same
user. The script uses the user's existing GNOME session bus and Ubuntu's PyGObject
package (`python3-gi`); no pip packages are required. If the selected Python cannot
import `gi`, the script restarts itself with `/usr/bin/python3`, preserving all
arguments. This also supports `python wake.py` inside an activated virtual
environment, even when its interpreter is a symlink to the system Python.

```bash
cd /home/sentice/sentice_admin/system/splashtop-wake
./wake.py
# Also works inside an activated virtual environment:
python wake.py
```

Connect in Splashtop when it prints **Ready to connect**. The default display wait
is eight seconds; use `./wake.py --wait-seconds 15` for a longer handshake, up to
60 seconds.

An awake display has power mode On and at least one detected monitor and active
desktop display. When these conditions hold, no input session or Shift keypress
is created and display power is left alone. A locked, powered-on display also
receives no wake input. `--quiet-if-awake` exits silently with status zero in
these cases; ordinary manual runs still report whether the desktop is locked.

## Every-minute cron job

`wake-cron.sh` runs the system Python, sets the session D-Bus environment for the
current user, and uses a nonblocking `flock` to prevent overlapping runs. It exits
silently when the user session bus is absent or the display is already awake.
Wake attempts and errors go to the system journal under `splashtop-wake`; the
wrapper creates no accumulating log file or cron email output.

Installed in user `sentice`'s crontab:

```cron
* * * * * /home/sentice/sentice_admin/system/splashtop-wake/wake-cron.sh
```

Inspect it with `crontab -l`; edit or remove the line with `crontab -e`.
Read results with `journalctl -t splashtop-wake`. The job wakes a sleeping
display on the next minute tick while GNOME is running. It does not boot or
resume a suspended computer; cron cannot run while the computer is suspended.

An active connected monitor or HDMI/DisplayPort dummy plug is required. The script
preserves the desktop's lock and reports if it needs unlocking. It does not create
a virtual display or change idle settings. The cron job restores display power
after sleep; awake checks do not reset the idle timer.
This is a display wake operation for an already running Ubuntu session.

Exit status: `0` ready, `1` no active display, `2` desktop locked, `3` GNOME/D-Bus
failure. Invalid command-line arguments also return `2` with an argparse error.

The script reproduces the native input/display sequence verified in this session;
its readiness check confirms local display availability and lock state. Splashtop
still handles the remote connection and screen-sharing permissions.

Run the isolated tests with `/usr/bin/python3 -m unittest discover -s . -p 'test_*.py'`.
They use a typed desktop fake and make no real D-Bus, display, or input calls.
