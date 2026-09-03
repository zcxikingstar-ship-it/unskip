# Changelog

Release notes for Unskip are kept here in reverse chronological order.

## [1.0.0] - 2026-09-03

Initial release.

### Added

- Static Git-diff review signals for common test-suite weakening patterns.
- Default staged, unstaged, and eligible untracked-file scanning against
  `HEAD`, with staged-only, base-ref, and supplied-diff modes.
- Text, JSON, and GitHub Actions output formats.
- Configurable high/medium/low failure thresholds and acknowledgement-aware
  exit codes.
- Same-hunk and deleted-file path acknowledgements with concrete review
  reasons.
- Python 3.9+ packaging with zero runtime dependencies and an `unskip` console
  script.
