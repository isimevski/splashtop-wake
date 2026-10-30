from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import shlex
import subprocess
import unittest
from unittest.mock import patch

import manage_cron as tool

PROJECT = Path("/home/desktop/dev/splashtop-wake")
OTHER_JOB = "MAILTO=desktop\n# Keep this backup\n0 3 * * * /usr/local/bin/backup\n"


class FakeCrontab(tool.UserCrontab):
    def __init__(self, document: str = "") -> None:
        self.document = document
        self.writes: list[str] = []
        self.reads = 0

    def read(self) -> str:
        self.reads += 1
        return self.document

    def write(self, document: str) -> None:
        self.writes.append(document)
        self.document = document


class CronPolicyTests(unittest.TestCase):
    def test_new_job_uses_checkout_path_every_minute(self) -> None:
        self.assertEqual("* * * * * /bin/sh /home/desktop/dev/splashtop-wake/wake-cron.sh "
                         "# managed-by: splashtop-wake\n", tool.cron_document("", PROJECT))

    def test_comments_settings_and_other_jobs_are_preserved(self) -> None:
        self.assertEqual(OTHER_JOB + tool.cron_entry(PROJECT) + "\n", tool.cron_document(OTHER_JOB, PROJECT))

    def test_repeated_setup_does_not_rewrite_or_duplicate_the_job(self) -> None:
        store = FakeCrontab(OTHER_JOB)
        self.assertTrue(tool.configure_cron(store, PROJECT))
        self.assertFalse(tool.configure_cron(store, PROJECT))
        self.assertEqual(1, len(store.writes))
        self.assertEqual(1, store.document.count(tool.MARKER))

    def test_setup_from_other_repository_moves_the_single_job(self) -> None:
        original = Path("/home/desktop/admin/system/splashtop-wake")
        store = FakeCrontab(OTHER_JOB + tool.cron_entry(original) + "\n")
        self.assertTrue(tool.configure_cron(store, PROJECT))
        self.assertEqual(OTHER_JOB + tool.cron_entry(PROJECT) + "\n", store.document)

    def test_legacy_jobs_from_both_repositories_are_migrated(self) -> None:
        legacy = "* * * * * /home/desktop/admin/system/splashtop-wake/wake-cron.sh\n"
        legacy += "* * * * * /bin/sh '/home/desktop/dev/splashtop-wake/wake-cron.sh'\n"
        self.assertEqual(OTHER_JOB + tool.cron_entry(PROJECT) + "\n",
                         tool.cron_document(legacy + OTHER_JOB, PROJECT))

    def test_unrelated_same_named_scripts_and_other_schedules_are_preserved(self) -> None:
        unrelated = "* * * * * /opt/other-tool/wake-cron.sh\n"
        unrelated += "0 * * * * /home/desktop/dev/splashtop-wake/wake-cron.sh\n"
        unrelated += "* * * * * /opt/splashtop-wake/wake-cron.sh && echo extra-command\n"
        self.assertEqual(unrelated + tool.cron_entry(PROJECT) + "\n", tool.cron_document(unrelated, PROJECT))

    def test_malformed_unrelated_lines_are_not_removed(self) -> None:
        malformed = "* * * * * '/unclosed quote\n"
        self.assertEqual(malformed + tool.cron_entry(PROJECT) + "\n", tool.cron_document(malformed, PROJECT))

    def test_removal_is_repeatable_and_preserves_other_jobs(self) -> None:
        store = FakeCrontab(OTHER_JOB + tool.cron_entry(PROJECT) + "\n")
        self.assertTrue(tool.configure_cron(store, None))
        self.assertEqual(OTHER_JOB, store.document)
        self.assertFalse(tool.configure_cron(store, None))
        self.assertEqual(1, len(store.writes))

    def test_removing_the_only_entry_leaves_an_empty_crontab(self) -> None:
        self.assertEqual("", tool.cron_document(tool.cron_entry(PROJECT) + "\n", None))

    def test_cron_path_quotes_spaces_apostrophes_percent_and_shell_characters(self) -> None:
        for project in (Path("/home/A B/it's 100%/splashtop-wake"), Path("/home/a/$(echo test);&/splashtop-wake")):
            with self.subTest(project=project):
                entry = tool.cron_entry(project)
                command = entry.split(maxsplit=5)[5].removesuffix(" " + tool.MARKER)
                self.assertNotIn("%", command.replace(r"\%", ""))
                self.assertEqual(["/bin/sh", str(project / "wake-cron.sh")],
                                 shlex.split(command.replace(r"\%", "%")))

    def test_invalid_path_fails_before_writing(self) -> None:
        for project in (Path("relative"), Path("/tmp/new\nline"), Path("/tmp/carriage\rreturn"), Path("/tmp/null\x00")):
            store = FakeCrontab(OTHER_JOB)
            with self.subTest(project=project), self.assertRaisesRegex(ValueError, "project path must be absolute"):
                tool.configure_cron(store, project)
            self.assertEqual([], store.writes)


class CrontabCommandTests(unittest.TestCase):
    def test_read_returns_the_existing_document_with_a_stable_locale(self) -> None:
        result = subprocess.CompletedProcess([], 0, OTHER_JOB, "")
        with patch.object(tool.subprocess, "run", return_value=result) as run:
            self.assertEqual(OTHER_JOB, tool.UserCrontab().read())
            self.assertEqual(["crontab", "-l"], run.call_args.args[0])
            self.assertEqual("C", run.call_args.kwargs["env"]["LC_ALL"])
            self.assertEqual(10, run.call_args.kwargs["timeout"])

    def test_only_no_crontab_is_treated_as_an_empty_schedule(self) -> None:
        result = subprocess.CompletedProcess([], 1, "", "no crontab for desktop\n")
        with patch.object(tool.subprocess, "run", return_value=result):
            self.assertEqual("", tool.UserCrontab().read())

    def test_read_errors_never_overwrite_existing_schedule(self) -> None:
        for code, error in ((1, "Permission denied"), (2, "no crontab for desktop"), (1, "")):
            result = subprocess.CompletedProcess([], code, "", error)
            with self.subTest(code=code, error=error), patch.object(tool.subprocess, "run", return_value=result) as run:
                with self.assertRaisesRegex(RuntimeError, "Cannot read crontab"):
                    tool.configure_cron(tool.UserCrontab(), PROJECT)
                self.assertEqual(1, run.call_count)

    def test_write_uses_stdin_without_a_shell(self) -> None:
        with patch.object(tool.subprocess, "run") as run:
            tool.UserCrontab().write(OTHER_JOB)
            run.assert_called_once_with(["crontab", "-"], input=OTHER_JOB, capture_output=True,
                                        text=True, check=True, timeout=10)


class CronCliTests(unittest.TestCase):
    def test_root_install_and_removal_are_rejected_without_accessing_crontab(self) -> None:
        store = FakeCrontab(OTHER_JOB)
        for action in ("install", "remove"):
            with patch.object(tool, "UserCrontab", return_value=store), patch.object(tool.os, "getuid", return_value=0):
                with redirect_stderr(StringIO()) as output:
                    self.assertEqual(1, tool.main([action]))
                    self.assertIn("without sudo", output.getvalue())
        self.assertEqual(0, store.reads)
        self.assertEqual([], store.writes)

    def test_status_shows_only_wake_jobs_and_never_writes(self) -> None:
        for existing in (OTHER_JOB, OTHER_JOB + tool.cron_entry(PROJECT) + "\n"):
            store = FakeCrontab(existing)
            with patch.object(tool, "UserCrontab", return_value=store), redirect_stdout(StringIO()) as output:
                self.assertEqual(0, tool.main(["status"]))
                expected = tool.cron_entry(PROJECT) if tool.MARKER in existing else "No Splashtop wake cron job is installed."
                self.assertEqual(expected + "\n", output.getvalue())
            self.assertEqual([], store.writes)

    def test_install_uses_this_checkout_and_remove_preserves_other_jobs(self) -> None:
        store = FakeCrontab(OTHER_JOB)
        with patch.object(tool, "UserCrontab", return_value=store), patch.object(tool.os, "getuid", return_value=1000):
            with redirect_stdout(StringIO()):
                self.assertEqual(0, tool.main([]))
                self.assertIn(tool.cron_entry(Path(tool.__file__).resolve().parent), store.document)
                self.assertEqual(0, tool.main(["remove"]))
        self.assertEqual(OTHER_JOB, store.document)

    def test_write_failures_and_timeouts_return_a_clear_error(self) -> None:
        errors = (subprocess.CalledProcessError(1, ["crontab", "-"], stderr="Bad cron entry\n"),
                  subprocess.TimeoutExpired("crontab", 10), OSError("crontab not found"))
        for error in errors:
            with patch.object(tool, "configure_cron", side_effect=error), patch.object(tool.os, "getuid", return_value=1000):
                with redirect_stderr(StringIO()) as output:
                    self.assertEqual(1, tool.main(["install"]))
                    self.assertIn("Cron setup failed:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
