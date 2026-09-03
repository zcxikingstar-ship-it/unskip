import tempfile
import unittest
from pathlib import Path

from unskip.diff import InputError, load_diff_file, parse_unified_diff


class DiffParserTests(unittest.TestCase):
    def test_parses_modified_lines_and_numbers(self):
        files = parse_unified_diff(
            """diff --git a/tests/a_test.py b/tests/a_test.py
index 1111111..2222222 100644
--- a/tests/a_test.py
+++ b/tests/a_test.py
@@ -4,2 +4,2 @@ def test_value():
-    assert value == 42
+    assert value
     cleanup()
"""
        )
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, "tests/a_test.py")
        self.assertEqual(files[0].status, "modified")
        removed, added, context = files[0].hunks[0].lines
        self.assertEqual((removed.old_line, removed.new_line), (4, None))
        self.assertEqual((added.old_line, added.new_line), (None, 4))
        self.assertEqual((context.old_line, context.new_line), (5, 5))

    def test_parses_deleted_and_renamed_files(self):
        files = parse_unified_diff(
            """diff --git a/tests/old_test.py b/tests/old_test.py
deleted file mode 100644
--- a/tests/old_test.py
+++ /dev/null
@@ -1 +0,0 @@
-assert True
diff --git a/tests/name_test.py b/tests/name_spec.py
similarity index 100%
rename from tests/name_test.py
rename to tests/name_spec.py
"""
        )
        self.assertEqual(files[0].status, "deleted")
        self.assertEqual(files[0].path, "tests/old_test.py")
        self.assertEqual(files[1].status, "renamed")
        self.assertEqual(files[1].old_path, "tests/name_test.py")
        self.assertEqual(files[1].new_path, "tests/name_spec.py")

    def test_reads_diff_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "change.diff"
            target.write_text(
                "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n",
                encoding="utf-8",
            )
            source, files, warnings = load_diff_file(str(target))
        self.assertEqual(source, str(target))
        self.assertEqual(len(files), 1)
        self.assertEqual(warnings, [])

    def test_rejects_malformed_header(self):
        with self.assertRaises(InputError):
            parse_unified_diff("diff --git only-one-path")

    def test_parses_quoted_path_with_spaces(self):
        files = parse_unified_diff(
            'diff --git "a/tests/space test.py" "b/tests/space test.py"\n'
            '--- "a/tests/space test.py"\n'
            '+++ "b/tests/space test.py"\n'
            "@@ -1 +1 @@\n-old\n+new\n"
        )
        self.assertEqual(files[0].path, "tests/space test.py")


if __name__ == "__main__":
    unittest.main()
