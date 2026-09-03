import unittest

from unskip.diff import parse_unified_diff
from unskip.model import Severity
from unskip.report import should_fail
from unskip.rules import analyze


def scan(diff_text):
    return analyze(parse_unified_diff(diff_text), "fixture")


def changed(path, before, after):
    return """diff --git a/{0} b/{0}
--- a/{0}
+++ b/{0}
@@ -1 +1 @@
-{1}
+{2}
""".format(path, before, after)


class RuleTests(unittest.TestCase):
    def test_added_skip_and_focus_are_high(self):
        result = scan(
            """diff --git a/tests/a.test.ts b/tests/a.test.ts
new file mode 100644
--- /dev/null
+++ b/tests/a.test.ts
@@ -0,0 +1,2 @@
+test.skip("broken", () => {});
+describe.only("one", () => {});
"""
        )
        self.assertEqual(
            {(item.rule_id, item.severity) for item in result.findings},
            {("skip-added", Severity.HIGH), ("focus-added", Severity.HIGH)},
        )

    def test_deleted_test_file_is_high(self):
        result = scan(
            """diff --git a/tests/old_test.py b/tests/old_test.py
deleted file mode 100644
--- a/tests/old_test.py
+++ /dev/null
@@ -1 +0,0 @@
-assert True
"""
        )
        ids = [item.rule_id for item in result.findings]
        self.assertIn("test-file-deleted", ids)
        self.assertIn("assertion-count-dropped", ids)

    def test_assertion_drop_and_comment_out(self):
        result = scan(
            """diff --git a/tests/a_test.py b/tests/a_test.py
--- a/tests/a_test.py
+++ b/tests/a_test.py
@@ -1,2 +1,2 @@
-assert result == 42
-assert other == 7
+# assert result == 42
+print(other)
"""
        )
        ids = [item.rule_id for item in result.findings]
        self.assertIn("assertion-count-dropped", ids)
        self.assertIn("assertion-commented-out", ids)

    def test_matcher_weakening_is_medium(self):
        result = scan(
            changed(
                "tests/value.test.ts",
                "expect(value).toStrictEqual({ id: 1 });",
                "expect(value).toBeDefined();",
            )
        )
        finding = next(
            item for item in result.findings if item.rule_id == "matcher-weakened"
        )
        self.assertEqual(finding.severity, Severity.MEDIUM)

    def test_timeout_and_tolerance_increases(self):
        result = scan(
            """diff --git a/tests/value_test.py b/tests/value_test.py
--- a/tests/value_test.py
+++ b/tests/value_test.py
@@ -1,2 +1,2 @@
-timeout = 5
-assert value == pytest.approx(10, abs_tol=0.01)
+timeout = 30
+assert value == pytest.approx(10, abs_tol=0.5)
"""
        )
        ids = [item.rule_id for item in result.findings]
        self.assertIn("timeout-increased", ids)
        self.assertIn("tolerance-widened", ids)

    def test_close_to_precision_drop(self):
        result = scan(
            changed(
                "tests/value.test.ts",
                "expect(value).toBeCloseTo(3.14159, 5);",
                "expect(value).toBeCloseTo(3.14159, 1);",
            )
        )
        self.assertIn("tolerance-widened", [item.rule_id for item in result.findings])

    def test_coverage_threshold_drop_is_high(self):
        result = scan(changed(".coveragerc", "fail_under = 90", "fail_under = 70"))
        finding = next(
            item
            for item in result.findings
            if item.rule_id == "coverage-threshold-lowered"
        )
        self.assertEqual(finding.severity, Severity.HIGH)

    def test_failure_masks(self):
        result = scan(
            """diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -1 +1,2 @@
 - run: npm test
+  continue-on-error: true
+  run: pytest || true
"""
        )
        findings = [
            item for item in result.findings if item.rule_id == "failure-mask-added"
        ]
        self.assertEqual(len(findings), 2)

    def test_coverage_exclusion_and_snapshot_change(self):
        exclusion = scan(
            """diff --git a/src/core.py b/src/core.py
--- a/src/core.py
+++ b/src/core.py
@@ -1 +1,2 @@
 def work():
+    return fallback()  # pragma: no cover
"""
        )
        snapshot = scan(
            """diff --git a/tests/__snapshots__/ui.snap b/tests/__snapshots__/ui.snap
--- a/tests/__snapshots__/ui.snap
+++ b/tests/__snapshots__/ui.snap
@@ -1 +1 @@
-old
+new
"""
        )
        self.assertEqual(exclusion.findings[0].rule_id, "coverage-exclusion-added")
        self.assertEqual(snapshot.findings[0].rule_id, "snapshot-changed")
        self.assertEqual(snapshot.findings[0].severity, Severity.LOW)

    def test_valid_same_hunk_acknowledgement(self):
        result = scan(
            """diff --git a/tests/a_test.py b/tests/a_test.py
--- a/tests/a_test.py
+++ b/tests/a_test.py
@@ -1 +1,2 @@
 def test_remote():
+    # unskip: allow skip-added -- upstream API is unavailable; issue #42
+    pytest.skip("tracked by issue #42")
"""
        )
        finding = next(item for item in result.findings if item.rule_id == "skip-added")
        self.assertTrue(finding.acknowledged)
        self.assertIn("issue #42", finding.acknowledgement_reason)
        self.assertFalse(should_fail(result, "high"))

    def test_acknowledgement_does_not_cross_hunks(self):
        result = scan(
            """diff --git a/tests/a_test.py b/tests/a_test.py
--- a/tests/a_test.py
+++ b/tests/a_test.py
@@ -1 +1,2 @@
 def test_one():
+    # unskip: allow skip-added -- issue #42
@@ -20 +21,2 @@ def test_two():
 pass
+pytest.skip("not acknowledged here")
"""
        )
        skip = next(item for item in result.findings if item.rule_id == "skip-added")
        self.assertFalse(skip.acknowledged)

    def test_invalid_acknowledgement_is_reported(self):
        result = scan(
            """diff --git a/tests/a_test.py b/tests/a_test.py
--- a/tests/a_test.py
+++ b/tests/a_test.py
@@ -1 +1,2 @@
 pass
+# unskip: allow skip-added
"""
        )
        self.assertEqual(result.findings[0].rule_id, "invalid-acknowledgement")

    def test_targeted_acknowledgement_can_review_deleted_test(self):
        result = scan(
            """diff --git a/tests/old_test.py b/tests/old_test.py
deleted file mode 100644
--- a/tests/old_test.py
+++ /dev/null
@@ -1 +0,0 @@
-assert True
diff --git a/docs/test-review.md b/docs/test-review.md
new file mode 100644
--- /dev/null
+++ b/docs/test-review.md
@@ -0,0 +1 @@
+unskip: allow *@tests/old_test.py -- replaced by tests/new_test.py in this change
"""
        )
        deleted_findings = [
            item for item in result.findings if item.path == "tests/old_test.py"
        ]
        self.assertTrue(deleted_findings)
        self.assertTrue(all(item.acknowledged for item in deleted_findings))
        self.assertFalse(should_fail(result, "low"))

    def test_non_test_application_change_is_clean(self):
        result = scan(changed("src/app.py", "return 1", "return 2"))
        self.assertEqual(result.findings, [])

    def test_documentation_example_is_not_treated_as_test_code(self):
        result = scan(
            changed("docs/testing.md", "Use test().", "Use test.skip() only locally.")
        )
        self.assertEqual(result.findings, [])

    def test_removed_assertion_comment_does_not_change_assertion_count(self):
        result = scan(
            changed("tests/a_test.py", "# assert the response shape", "# verify shape")
        )
        self.assertEqual(result.findings, [])


if __name__ == "__main__":
    unittest.main()
