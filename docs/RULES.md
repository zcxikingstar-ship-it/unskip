# Unskip rule catalog

Unskip reports static signals in a Git diff. The rule ID in this table is the
exact `RULE_ID` accepted by an acknowledgement. Severity controls the default
review threshold; it is not a claim about intent or actual behavior.

| Rule ID | Severity | Signal | Review question |
| --- | --- | --- | --- |
| `test-file-deleted` | high | A test file is deleted. | Is the deletion required, and where did the coverage move? |
| `skip-added` | high | A test skip marker or equivalent is added. | Is the skipped case explicitly justified and tracked? |
| `focus-added` | high | A focused or exclusive test selector is added. | Could this cause the suite to run only a subset of tests? |
| `assertion-commented-out` | high | An assertion is commented out. | What behavior is no longer checked? |
| `assertion-count-dropped` | medium | Assertions are removed from a test. | Was an assertion intentionally replaced, or was coverage lost? |
| `matcher-weakened` | medium | An assertion matcher is changed to a broader or less strict form. | Does the new matcher still distinguish the failure being tested? |
| `timeout-increased` | medium | A test timeout or deadline is increased. | Is the slower limit supported by a measured runtime change? |
| `tolerance-widened` | medium | An accepted numeric or comparison tolerance is widened. | Does the wider tolerance still catch the intended regression? |
| `coverage-threshold-lowered` | high | A configured coverage threshold is lowered. | Why is the quality gate being reduced, and what replaces it? |
| `failure-mask-added` | high | New logic masks, swallows, suppresses, or converts a test failure into success. | Is the failure still observable by the test runner and reviewer? |
| `coverage-exclusion-added` | medium | A new coverage exclusion is added. | Is the excluded code genuinely unreachable or tested elsewhere? |
| `snapshot-changed` | low | A snapshot or golden output is changed. | Was the expected behavior reviewed rather than merely regenerated? |
| `invalid-acknowledgement` | medium | An acknowledgement is malformed, unsupported, or missing a usable reason. | Can the intended exception be tied to a valid rule and concrete reason? |

## Acknowledgements

An acknowledgement must be in the same unified-diff hunk as the finding and
must use this form:

```text
unskip: allow RULE_ID -- concrete reason
```

For example:

```text
unskip: allow snapshot-changed -- output changes with the approved API version
```

The rule ID must match this catalog exactly. The reason is part of the review
record; a vague reason or a line outside the finding's hunk does not make the
finding acknowledged and may produce `invalid-acknowledgement`.

A deleted file has no added line in its own hunk, so it can use a path-targeted
acknowledgement on any added line in the diff:

```text
unskip: allow *@tests/legacy_test.py -- coverage moved to tests/test_api.py
```

The path must match the deleted path exactly. Replace `*` with
`test-file-deleted` to limit the acknowledgement to that rule.

Acknowledged findings remain in the result set. Human-readable output includes
them when `--show-acknowledged` is supplied, and JSON output keeps them visible
for counting and audit. An acknowledgement changes exit-code eligibility, not
the underlying evidence.

## Thresholds

The default `--fail-on medium` threshold fails only for unacknowledged high or
medium findings. `low` includes all severities; `high` includes only high;
`never` reports without failing for findings. Findings below the threshold and
acknowledged findings do not produce exit code `1`. Usage, Git, and input
errors produce exit code `2`.

## Reading a finding

Review the changed lines, the surrounding hunk, and the test or configuration
context. A rule is a prompt to investigate a possible weakening, not a
substitute for running the project's own test and coverage commands. Unskip
does not run those commands and does not infer intent from authorship.
