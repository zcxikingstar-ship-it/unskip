# Unskip

Catch test-suite weakening in your Git diff.

Unskip is a local, static review tool for changes that may make a test suite
less meaningful. It reports review signals such as newly skipped tests,
commented-out assertions, relaxed matchers, and lowered coverage gates.

These are signals for a human reviewer, not proof of cheating or correctness.
Unskip never runs target code and never uploads data.

A test runner answers “does the suite pass?” Unskip asks a different question:
“did this diff make the suite easier to pass?” It complements normal tests and
coverage gates instead of replacing them.

## Install

Install from a GitHub checkout or another source checkout. There is no PyPI
installation step assumed by this release:

```sh
cd unskip
python -m pip install .
```

Unskip has zero runtime dependencies and supports Python 3.9 or newer. Build
tooling is only needed when building a distribution:

```sh
python -m pip install --upgrade build
python -m build
```

## Quick demo

Review the supplied Git unified diff and return a failure for an unacknowledged
medium-or-higher signal:

```sh
unskip --diff examples/weakening.diff --format text --fail-on medium
```

Inspect every finding as JSON without failing the shell while you review it:

```sh
unskip --diff examples/weakening.diff --format json --fail-on never
```

The same input can be streamed on standard input:

```sh
git diff HEAD | unskip --diff - --format github
```

## What gets scanned

With no mode-selection flag, Unskip scans staged and unstaged tracked changes
against `HEAD`, plus eligible untracked test and test-configuration files.
The optional `PATH` argument names the repository to inspect and defaults to
the current directory.

The three mode-selection flags are mutually exclusive:

| Invocation | Input |
| --- | --- |
| `unskip [PATH]` | Staged and unstaged tracked changes against `HEAD`, plus eligible untracked test/config files |
| `unskip [PATH] --staged` | The index only |
| `unskip [PATH] --base REF` | The `REF...HEAD` comparison |
| `unskip [PATH] --diff FILE` | A supplied Git unified diff; `FILE` may be `-` for standard input |

Use `--no-untracked` with a Git-backed scan to exclude eligible untracked
files. A supplied diff is read as input rather than regenerated from the
working tree.

## CLI reference

```text
unskip [PATH]
  --staged
  --base REF
  --diff FILE
  --format text|json|github
  --fail-on high|medium|low|never
  --show-acknowledged
  --no-untracked
  --version
```

`--staged`, `--base`, and `--diff` cannot be combined. The default output is
text. `--format json` is intended for integrations and keeps acknowledged
findings in the result; `--format github` emits GitHub Actions-friendly review
annotations. The default failure threshold is `medium`.

Severity is ordered high, medium, then low. `--fail-on never` reports findings
without making them fail the command. `--show-acknowledged` includes
acknowledged findings in human-readable output; JSON keeps them visible so
that automation can count them separately.

See the [complete rule table](docs/RULES.md) for rule IDs, severities, and
review guidance.

## Acknowledging an intentional change

Place this exact syntax in the same diff hunk as the finding, in a comment or
other file-appropriate text:

```text
unskip: allow tolerance-widened -- the public API rounds values to two decimals
```

`RULE_ID` must be one of the IDs in the rule table, and the reason must be
concrete. Acknowledgement does not remove the finding: it remains countable
and is visible with `--show-acknowledged` and in JSON output. Review the reason
alongside the code change.

An unscoped `*` is rejected: same-hunk acknowledgements must name one rule.

For a deleted test file, place a path-targeted acknowledgement anywhere in an
added line of the diff. The path must match the deleted path exactly:

```text
unskip: allow *@tests/legacy_test.py -- coverage moved to tests/test_api.py
```

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | No findings at or above the threshold, or all such findings are acknowledged |
| `1` | At least one unacknowledged finding is at or above the threshold |
| `2` | Usage, Git, or input error |

## GitHub Actions

This minimal job installs from the checkout, fetches enough history for a base
comparison, and emits review annotations:

```yaml
name: Unskip

on:
  pull_request:

permissions:
  contents: read

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install .
      - run: >-
          unskip --base "${{ github.event.pull_request.base.sha }}"
          --format github --fail-on medium
```

## Pre-commit

After installing Unskip into the environment used by pre-commit, add a local
hook that checks the index before each commit:

```yaml
repos:
  - repo: local
    hooks:
      - id: unskip
        name: Unskip test-suite weakening review
        entry: unskip --staged --fail-on medium
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
```

## Limitations

- Unskip uses static diff and file signals. It does not prove that a person or
  an AI system cheated, and it does not prove that the resulting tests are
  correct.
- It never runs the target project, its tests, or its build scripts. A clean
  Unskip result is not a passing test run.
- It can miss semantic weakening that is not represented by a recognizable
  diff pattern, and it can report intentional maintenance as a false positive.
- Framework-specific syntax, generated files, unusual test layouts, and
  changes outside the supplied diff may limit the evidence available to the
  scanner.
- Git-backed modes need a usable repository and comparison state. Use
  `--diff FILE` when a Git-format diff is produced by another system. Non-empty
  input without `diff --git` headers is rejected instead of treated as clean.
- An acknowledgement records a reason for review; it is not an approval,
  authentication mechanism, or correctness claim.

## Threat model and privacy

Unskip is designed to inspect local Git metadata, diff text, and eligible local
files. It has no runtime dependencies, does not require a network service, and
never uploads scan data. It never executes target code, including code found
in a diff. Keep normal repository permissions in place and avoid passing
confidential content to third-party wrappers around the CLI.

The output is intentionally evidence for review rather than a verdict. Treat
both findings and acknowledgements as untrusted input until a reviewer checks
the surrounding change. Report security issues using [SECURITY.md](SECURITY.md).

## Evidence and framing

The problem framing is informed by reports in
[anthropics/claude-code issue #319](https://github.com/anthropics/claude-code/issues/319),
which describes tests being changed so they pass, and
[issue #45550](https://github.com/anthropics/claude-code/issues/45550),
which describes failing tests being marked with `@unittest.skip`. These are
reports of observed behavior, not proof that any particular change is
malicious or that a tool can determine intent.

## Project files

- [Rule catalog](docs/RULES.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## License

Unskip is released under the [MIT License](LICENSE).
