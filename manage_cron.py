#!/usr/bin/python3
"""Manage this desktop user's single Splashtop wake cron job."""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys

MARKER = "# managed-by: splashtop-wake"


def is_wake_job(line: str) -> bool:
    if line.rstrip().endswith(MARKER):
        return True
    fields = line.split(maxsplit=5)
    if len(fields) != 6 or fields[:5] != ["*"] * 5:
        return False
    try:
        command = shlex.split(fields[5], comments=True)
    except ValueError:
        return False
    if command and command[0] in {"sh", "/bin/sh", "/usr/bin/sh"}:
        command = command[1:]
    return len(command) == 1 and PurePosixPath(command[0]).parts[-2:] == ("splashtop-wake", "wake-cron.sh")


def cron_entry(project: Path) -> str:
    script = str(project / "wake-cron.sh")
    if not project.is_absolute() or any(character in script for character in "\n\r\x00"):
        raise ValueError("The project path must be absolute and contain no newline, carriage return, or NUL.")
    command = shlex.quote(script).replace("%", r"\%")
    return f"* * * * * /bin/sh {command} {MARKER}"


def cron_document(existing: str, project: Path | None) -> str:
    lines = [line for line in existing.splitlines() if not is_wake_job(line)]
    if project is not None:
        lines.append(cron_entry(project))
    return "\n".join(lines) + ("\n" if lines else "")


class UserCrontab:
    def read(self) -> str:
        environment = dict(os.environ, LC_ALL="C")
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                                env=environment, check=False, timeout=10)
        if result.returncode == 0:
            return result.stdout
        if result.returncode == 1 and result.stderr.strip().startswith("no crontab for "):
            return ""
        raise RuntimeError(f"Cannot read crontab: {result.stderr.strip() or f'exit {result.returncode}'}")

    def write(self, document: str) -> None:
        subprocess.run(["crontab", "-"], input=document, capture_output=True, text=True,
                       check=True, timeout=10)


def configure_cron(store: UserCrontab, project: Path | None) -> bool:
    previous = store.read()
    updated = cron_document(previous, project)
    if previous == updated:
        return False
    store.write(updated)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "remove", "status"), default="install", nargs="?")
    action = parser.parse_args(argv).action
    try:
        store = UserCrontab()
        if action == "status":
            jobs = [line for line in store.read().splitlines() if is_wake_job(line)]
            print("\n".join(jobs) if jobs else "No Splashtop wake cron job is installed.")
            return 0
        if os.getuid() == 0:
            raise RuntimeError("Run as your logged-in desktop user, without sudo.")
        project = Path(__file__).resolve().parent if action == "install" else None
        changed = configure_cron(store, project)
        print("Crontab updated." if changed else "Crontab already up to date.")
        if project is not None:
            print(cron_entry(project))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        print(f"Cron setup failed: {detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
