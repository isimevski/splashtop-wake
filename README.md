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

## Setup and use

Run setup as the logged-in desktop user, without `sudo` in front of Make:

```bash
cd /path/to/splashtop-wake
make setup
make cron-status
make run
```

This works from either `~/dev/splashtop-wake` or the `system/splashtop-wake`
directory in the parent repository. The checkout where you run setup becomes the
one used by cron. Install Make first if needed: `sudo apt-get install make`.

`setup.sh` checks `/usr/bin/python3` and GNOME's PyGObject bindings. On
Debian/Ubuntu it installs missing `python3`, `python3-gi`, and
`gir1.2-glib-2.0` packages, plus the required cron/utility packages when missing.
It uses `sudo` for system packages and to enable/start `cron.service` when needed
on systemd machines. The crontab itself always belongs to the desktop user.
No pip packages or virtual environment are needed: GNOME bindings come from the
system Python. Other distributions require equivalent system packages and a
running cron daemon; automatic package/service setup targets Debian/Ubuntu.

For individual setup steps:

```bash
make setup-python  # Check/install system Python and GNOME bindings only
make install-cron  # Check dependencies and install/update the user cron job
make remove-cron   # Remove the wake job while preserving unrelated jobs
```

You can also run `bash setup.sh`, `bash setup.sh python`, or
`bash setup.sh cron` directly. `make help` lists the available commands.

For a manual wake without installing a cron job:

```bash
/usr/bin/python3 wake.py
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

`make setup` or `make install-cron` installs an entry with the current checkout's
absolute path, for example:

```cron
* * * * * /bin/sh /home/you/dev/splashtop-wake/wake-cron.sh # managed-by: splashtop-wake
```

Repeated setup keeps exactly one wake job. Running it from the other checkout
moves that job to the other path. Existing every-minute `splashtop-wake/wake-cron.sh`
entries from the original manual installation are migrated to the managed entry;
unrelated jobs, comments, and environment settings are preserved. Paths with
spaces or percent signs are quoted/escaped for cron. A failed crontab read stops
setup without overwriting the existing schedule.

Inspect the wake entry with `make cron-status`, or the full schedule with
`crontab -l`. Remove the wake entry with `make remove-cron`; `crontab -e`
also remains available for manual edits.
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

Run the isolated tests with `make test`, or
`/usr/bin/python3 -B -m unittest discover -s . -p 'test_*.py' -v`.
They use desktop/crontab fakes and make no real D-Bus, display, input, or crontab
changes. Cron tests cover repeated installation, migration between checkouts,
legacy entries, preservation of other jobs, safe paths, removal, and read/write
failures.
