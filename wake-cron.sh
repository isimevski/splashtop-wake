#!/bin/sh
set -eu

project_directory=$(/usr/bin/dirname -- "$(/usr/bin/readlink -f -- "$0")")
session_runtime="/run/user/$(/usr/bin/id -u)"
export XDG_RUNTIME_DIR="$session_runtime"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$session_runtime/bus"

if [ ! -S "$session_runtime/bus" ]; then
    exit 0
fi

wake_status=0
wake_output=$(/usr/bin/flock --nonblock --conflict-exit-code 0 "$session_runtime/splashtop-wake.lock" \
    /usr/bin/python3 "$project_directory/wake.py" --quiet-if-awake 2>&1) || wake_status=$?

if [ -n "$wake_output" ]; then
    /usr/bin/logger --tag splashtop-wake -- "$wake_output"
fi
exit "$wake_status"
