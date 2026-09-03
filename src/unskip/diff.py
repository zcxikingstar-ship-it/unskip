from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .model import DiffLine, FileDiff, Hunk
from .paths import is_relevant_untracked, normalized

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$")
MAX_UNTRACKED_BYTES = 1_000_000


class InputError(RuntimeError):
    pass


def _strip_git_prefix(path: str) -> str:
    if path in {"/dev/null", "dev/null"}:
        return "/dev/null"
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _decode_header_path(value: str) -> str:
    value = value.split("\t", 1)[0].strip()
    if value.startswith('"'):
        try:
            parsed = shlex.split(value)
            if parsed:
                value = parsed[0]
        except ValueError:
            pass
    return _strip_git_prefix(value)


def parse_unified_diff(text: str) -> List[FileDiff]:
    files: List[FileDiff] = []
    current: Optional[FileDiff] = None
    hunk: Optional[Hunk] = None
    old_line = 0
    new_line = 0

    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            try:
                parts = shlex.split(raw[len("diff --git ") :])
            except ValueError as exc:
                raise InputError("invalid diff header: {}".format(raw)) from exc
            if len(parts) < 2:
                raise InputError("invalid diff header: {}".format(raw))
            current = FileDiff(
                old_path=_strip_git_prefix(parts[0]),
                new_path=_strip_git_prefix(parts[1]),
            )
            files.append(current)
            hunk = None
            continue

        if current is None:
            continue
        if raw.startswith("new file mode "):
            current.status = "added"
            continue
        if raw.startswith("deleted file mode "):
            current.status = "deleted"
            continue
        if raw.startswith("rename from "):
            current.status = "renamed"
            current.old_path = _decode_header_path(raw[len("rename from ") :])
            continue
        if raw.startswith("rename to "):
            current.status = "renamed"
            current.new_path = _decode_header_path(raw[len("rename to ") :])
            continue
        if raw.startswith("Binary files ") or raw == "GIT binary patch":
            current.binary = True
            continue
        if raw.startswith("--- "):
            current.old_path = _decode_header_path(raw[4:])
            if current.old_path == "/dev/null":
                current.status = "added"
            continue
        if raw.startswith("+++ "):
            current.new_path = _decode_header_path(raw[4:])
            if current.new_path == "/dev/null":
                current.status = "deleted"
            continue

        match = HUNK_RE.match(raw)
        if match:
            old_line = int(match.group(1))
            new_line = int(match.group(2))
            hunk = Hunk(old_start=old_line, new_start=new_line, header=raw)
            current.hunks.append(hunk)
            continue

        if hunk is None or not raw:
            continue
        prefix = raw[0]
        body = raw[1:]
        if prefix == "+":
            hunk.lines.append(DiffLine("add", body, None, new_line))
            new_line += 1
        elif prefix == "-":
            hunk.lines.append(DiffLine("remove", body, old_line, None))
            old_line += 1
        elif prefix == " ":
            hunk.lines.append(DiffLine("context", body, old_line, new_line))
            old_line += 1
            new_line += 1
        elif prefix == "\\":
            continue

    return files


def _run_git(root: Path, args: Sequence[str]) -> bytes:
    try:
        process = subprocess.run(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise InputError("git is required but was not found in PATH") from exc
    if process.returncode != 0:
        message = process.stderr.decode("utf-8", "replace").strip()
        raise InputError(message or "git command failed")
    return process.stdout


def find_repo(path: str) -> Path:
    candidate = Path(path).expanduser().resolve()
    if candidate.is_file():
        candidate = candidate.parent
    output = _run_git(candidate, ["rev-parse", "--show-toplevel"])
    return Path(output.decode("utf-8", "surrogateescape").strip())


def _resolve_base(root: Path, base: str) -> str:
    resolved = (
        _run_git(
            root,
            ["rev-parse", "--verify", "--end-of-options", "{}^{{commit}}".format(base)],
        )
        .decode("ascii", "replace")
        .strip()
    )
    head = (
        _run_git(root, ["rev-parse", "--verify", "HEAD^{commit}"])
        .decode("ascii", "replace")
        .strip()
    )
    return (
        _run_git(root, ["merge-base", resolved, head])
        .decode("ascii", "replace")
        .strip()
    )


def _untracked_file(path: str, content: str) -> FileDiff:
    lines = content.splitlines()
    hunk = Hunk(old_start=0, new_start=1, header="@@ -0,0 +1,{} @@".format(len(lines)))
    for index, line in enumerate(lines, 1):
        hunk.lines.append(DiffLine("add", line, None, index))
    return FileDiff(
        old_path="/dev/null", new_path=normalized(path), status="added", hunks=[hunk]
    )


def _load_untracked(root: Path) -> Tuple[List[FileDiff], List[str]]:
    output = _run_git(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    files: List[FileDiff] = []
    warnings: List[str] = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        rel = os.fsdecode(raw)
        if not is_relevant_untracked(rel):
            continue
        target = root / rel
        try:
            if not target.is_file() or target.is_symlink():
                continue
            size = target.stat().st_size
            if size > MAX_UNTRACKED_BYTES:
                warnings.append("skipped untracked file over 1 MB: {}".format(rel))
                continue
            data = target.read_bytes()
        except OSError as exc:
            warnings.append("could not read untracked file {}: {}".format(rel, exc))
            continue
        if b"\0" in data:
            warnings.append("skipped binary untracked file: {}".format(rel))
            continue
        files.append(_untracked_file(rel, data.decode("utf-8", "replace")))
    return files, warnings


def load_git_diff(
    path: str,
    staged: bool = False,
    base: Optional[str] = None,
    include_untracked: bool = True,
) -> Tuple[str, List[FileDiff], List[str]]:
    root = find_repo(path)
    common = [
        "-c",
        "core.quotePath=false",
        "diff",
        "--no-ext-diff",
        "--no-color",
        "--unified=3",
        "--find-renames",
    ]
    if staged:
        args = [*common, "--cached", "--"]
        source = "staged changes"
    elif base is not None:
        merge_base = _resolve_base(root, base)
        args = [*common, merge_base, "HEAD", "--"]
        source = "{}...HEAD".format(base)
    else:
        _run_git(root, ["rev-parse", "--verify", "HEAD^{commit}"])
        args = [*common, "HEAD", "--"]
        source = "working tree vs HEAD"

    diff_text = _run_git(root, args).decode("utf-8", "replace")
    files = parse_unified_diff(diff_text)
    warnings: List[str] = []
    if include_untracked and not staged and base is None:
        extra, extra_warnings = _load_untracked(root)
        seen = {item.path for item in files}
        files.extend(item for item in extra if item.path not in seen)
        warnings.extend(extra_warnings)
    return source, files, warnings


def load_diff_file(filename: str) -> Tuple[str, List[FileDiff], List[str]]:
    if filename == "-":
        import sys

        text = sys.stdin.read()
        source = "stdin"
    else:
        target = Path(filename).expanduser()
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise InputError(
                "could not read diff file {}: {}".format(filename, exc)
            ) from exc
        source = str(target)
    return source, parse_unified_diff(text), []
