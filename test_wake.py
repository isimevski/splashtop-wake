from __future__ import annotations

import argparse
import contextlib
import io
import unittest

from wake import DISPLAY_POWER_ON, GnomeDesktop, wake_if_needed


class FakeDesktop(GnomeDesktop):
    def __init__(self, power_mode: int = DISPLAY_POWER_ON, displays: tuple[int, int] = (1, 1), is_locked: bool = False) -> None:
        self.power_mode = power_mode
        self.display_counts = displays
        self.is_screen_locked = is_locked
        self.wake_calls = 0
        self.can_restore_display = True

    def display_power(self) -> int:
        return self.power_mode

    def displays(self) -> tuple[int, int]:
        return self.display_counts

    def is_locked(self) -> bool:
        return self.is_screen_locked

    def wake(self) -> None:
        self.wake_calls += 1
        if self.can_restore_display:
            self.power_mode = DISPLAY_POWER_ON
            self.display_counts = (1, 1)


class WakeTest(unittest.TestCase):
    def run_wake(self, desktop: FakeDesktop, is_quiet: bool = False) -> tuple[int, str]:
        output = io.StringIO()
        options = argparse.Namespace(wait_seconds=0, quiet_if_awake=is_quiet)
        with contextlib.redirect_stdout(output):
            result = wake_if_needed(desktop, options)
        return result, output.getvalue()

    def test_awake_requires_power_on_and_an_active_monitor(self) -> None:
        cases = [(0, (1, 1), True), (1, (1, 1), False), (2, (1, 1), False), (3, (1, 1), False),
                 (0, (0, 0), False), (0, (1, 0), False), (0, (0, 1), False)]
        for power_mode, displays, expected in cases:
            with self.subTest(power=power_mode, displays=displays):
                self.assertEqual(expected, FakeDesktop(power_mode, displays).is_awake())

    def test_awake_desktop_receives_no_input(self) -> None:
        desktop = FakeDesktop()
        result, output = self.run_wake(desktop)
        self.assertEqual(0, result)
        self.assertEqual(0, desktop.wake_calls)
        self.assertIn("Display already awake; no wake input sent.", output)
        self.assertIn("Ready to connect", output)

    def test_cron_is_silent_and_sends_no_input_when_awake_even_if_locked(self) -> None:
        for is_locked in (False, True):
            with self.subTest(is_locked=is_locked):
                desktop = FakeDesktop(is_locked=is_locked)
                self.assertEqual((0, ""), self.run_wake(desktop, True))
                self.assertEqual(0, desktop.wake_calls)

    def test_sleeping_display_is_woken_once_and_then_skipped(self) -> None:
        desktop = FakeDesktop(3)
        result, output = self.run_wake(desktop, True)
        self.assertEqual(0, result)
        self.assertEqual(1, desktop.wake_calls)
        self.assertIn("Sent native Wayland Shift press/release", output)
        self.assertEqual((0, ""), self.run_wake(desktop, True))
        self.assertEqual(1, desktop.wake_calls)

    def test_missing_display_is_reported_after_one_wake_attempt(self) -> None:
        desktop = FakeDesktop(3, (0, 0))
        desktop.can_restore_display = False
        result, output = self.run_wake(desktop)
        self.assertEqual(1, result)
        self.assertEqual(1, desktop.wake_calls)
        self.assertIn("No active display detected.", output)

    def test_manual_run_reports_a_lock_without_waking_an_awake_display(self) -> None:
        desktop = FakeDesktop(is_locked=True)
        result, output = self.run_wake(desktop)
        self.assertEqual(2, result)
        self.assertEqual(0, desktop.wake_calls)
        self.assertIn("desktop is locked", output)


if __name__ == "__main__":
    unittest.main()
