import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from unskip.cli import main

ROOT = Path(__file__).resolve().parents[1]


def run_cli(args):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def git(repo, *args):
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.returncode:
        raise AssertionError(process.stderr)
    return process.stdout


class CliTests(unittest.TestCase):
    def test_example_diff_fails_and_json_is_machine_readable(self):
        code, stdout, stderr = run_cli(
            ["--diff", str(ROOT / "examples" / "weakening.diff"), "--format", "json"]
        )
        payload = json.loads(stdout)
        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertGreaterEqual(payload["summary"]["high"], 2)
        self.assertEqual(payload["tool"], "unskip")

    def test_low_findings_do_not_fail_default_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.diff"
            path.write_text(
                """diff --git a/tests/__snapshots__/a.snap b/tests/__snapshots__/a.snap
--- a/tests/__snapshots__/a.snap
+++ b/tests/__snapshots__/a.snap
@@ -1 +1 @@
-old
+new
""",
                encoding="utf-8",
            )
            code, stdout, _ = run_cli(["--diff", str(path)])
        self.assertEqual(code, 0)
        self.assertIn("snapshot-changed", stdout)

    def test_invalid_repo_is_operational_error(self):
        with tempfile.TemporaryDirectory() as directory:
            code, _, stderr = run_cli([directory])
        self.assertEqual(code, 2)
        self.assertIn("not a git repository", stderr.lower())

    def test_default_includes_relevant_untracked_files(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("demo\n", encoding="utf-8")
            git(repo, "add", "README.md")
            git(repo, "commit", "-qm", "initial")
            tests = repo / "tests"
            tests.mkdir()
            (tests / "new_test.py").write_text(
                '@unittest.skip("later")\ndef test_new():\n    assert True\n',
                encoding="utf-8",
            )
            code, stdout, _ = run_cli([str(repo)])
            clean_code, clean_stdout, _ = run_cli([str(repo), "--no-untracked"])
        self.assertEqual(code, 1)
        self.assertIn("skip-added", stdout)
        self.assertEqual(clean_code, 0)
        self.assertIn("0 changed files", clean_stdout)

    def test_staged_mode_ignores_unstaged_then_detects_staged(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            tests = repo / "tests"
            tests.mkdir()
            target = tests / "value_test.py"
            target.write_text(
                "def test_value():\n    assert value == 42\n", encoding="utf-8"
            )
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "initial")
            target.write_text(
                '@unittest.skip("later")\ndef test_value():\n    assert value == 42\n',
                encoding="utf-8",
            )
            clean_code, _, _ = run_cli([str(repo), "--staged"])
            git(repo, "add", "tests/value_test.py")
            finding_code, stdout, _ = run_cli([str(repo), "--staged"])
        self.assertEqual(clean_code, 0)
        self.assertEqual(finding_code, 1)
        self.assertIn("skip-added", stdout)

    def test_never_threshold_reports_but_does_not_fail(self):
        code, stdout, _ = run_cli(
            [
                "--diff",
                str(ROOT / "examples" / "weakening.diff"),
                "--fail-on",
                "never",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("skip-added", stdout)

    def test_base_mode_scans_committed_feature_change(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            tests = repo / "tests"
            tests.mkdir()
            target = tests / "value_test.py"
            target.write_text(
                "def test_value():\n    assert value == 42\n", encoding="utf-8"
            )
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "base")
            base = git(repo, "rev-parse", "HEAD").strip()
            target.write_text(
                '@unittest.skip("later")\ndef test_value():\n    assert value == 42\n',
                encoding="utf-8",
            )
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "weaken test")
            code, stdout, stderr = run_cli([str(repo), "--base", base])
        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertIn("skip-added", stdout)

    def test_github_format_emits_annotations(self):
        code, stdout, _ = run_cli(
            ["--diff", str(ROOT / "examples" / "weakening.diff"), "--format", "github"]
        )
        self.assertEqual(code, 1)
        self.assertIn("::error file=tests/math.test.ts", stdout)
        self.assertIn("title=unskip/skip-added", stdout)


if __name__ == "__main__":
    unittest.main()
