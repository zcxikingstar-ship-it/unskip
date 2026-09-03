from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .diff import InputError, load_diff_file, load_git_diff
from .report import render_github, render_json, render_text, should_fail
from .rules import analyze


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="unskip",
        description="Catch test-suite weakening in your Git diff.",
    )
    parser.add_argument(
        "path", nargs="?", default=".", help="Git repository path (default: .)"
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--staged", action="store_true", help="scan only staged changes"
    )
    source.add_argument("--base", metavar="REF", help="scan commits in REF...HEAD")
    source.add_argument(
        "--diff",
        metavar="FILE",
        help="scan a unified diff file; use - for stdin",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "github"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--fail-on",
        choices=("high", "medium", "low", "never"),
        default="medium",
        help="minimum severity that exits 1 (default: medium)",
    )
    parser.add_argument(
        "--show-acknowledged",
        action="store_true",
        help="include acknowledged findings in text/GitHub output",
    )
    parser.add_argument(
        "--no-untracked",
        action="store_true",
        help="exclude eligible untracked files from the default working-tree scan",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s {}".format(__version__)
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.diff is not None:
            source, files, warnings = load_diff_file(args.diff)
        else:
            source, files, warnings = load_git_diff(
                args.path,
                staged=args.staged,
                base=args.base,
                include_untracked=not args.no_untracked,
            )
        result = analyze(files, source, warnings)
    except InputError as exc:
        print("unskip: {}".format(exc), file=sys.stderr)
        return 2

    if args.format == "json":
        output = render_json(result)
    elif args.format == "github":
        output = render_github(result, args.show_acknowledged)
    else:
        output = render_text(result, args.show_acknowledged)
    print(output)
    return 1 if should_fail(result, args.fail_on) else 0
