# Contributing to Unskip

Thanks for helping keep test changes reviewable. Contributions should preserve
the project's small, local, static-scanning contract.

## Development setup

Use Python 3.9 or newer and work from the repository root:

```sh
python -m venv .venv
python -m pip install --upgrade pip build
```

Activate `.venv` using the command for your shell, then install the checkout:

```sh
python -m pip install .
```

The package must keep zero runtime dependencies. Build tools such as `build`
are development or packaging dependencies only.

## Required checks

Run the standard-library test suite:

```sh
python -m unittest discover -s tests -v
```

Compile the source tree and build both distribution formats:

```sh
python -m compileall -q src
python -m build
```

Before opening a change, also smoke-test the installed console script:

```sh
unskip --version
```

The GitHub Actions workflow runs these checks on Linux, macOS, and Windows for
the minimum supported Python and a current supported Python.

## Change guidelines

- Keep detection static: Unskip must not execute target code, tests, or build
  scripts.
- Keep scan data local: Unskip must not upload diff or repository content.
- Preserve the CLI contract, including the mutually exclusive input modes,
  output formats, threshold behavior, acknowledgement syntaxes, and exit
  codes.
- When changing a rule, update [docs/RULES.md](docs/RULES.md), add or adjust
  focused tests, and document any intentional severity change.
- Keep user-facing messages actionable and avoid claiming that a finding proves
  intent or correctness.
- Keep changes focused; do not add a runtime dependency for a convenience that
  the standard library can provide.

## Pull requests

Describe the behavior being changed and the evidence used to verify it. A
useful pull request includes the relevant test command output, packaging or
CLI impact, and any known false-positive or false-negative boundary. Do not
include secrets or private repository content in the pull request.
