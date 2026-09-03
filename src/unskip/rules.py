from __future__ import annotations

import difflib
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .model import DiffLine, FileDiff, Finding, Hunk, ScanResult, Severity
from .paths import (
    is_ci_path,
    is_code_path,
    is_command_config_path,
    is_coverage_path,
    is_snapshot_path,
    is_test_path,
    normalized,
)

ASSERTION_RE = re.compile(
    r"(?:\bassert(?:ion)?\b|\bexpect\s*\(|\bshould\b|"
    r"\b(?:assert|require)\.(?:equal|notEqual|true|false|nil|noError|error|contains)\b|"
    r"\bassert_(?:eq|ne|matches)!\s*\(|\bassert[A-Z]\w*\s*\()",
    re.IGNORECASE,
)
SKIP_PATTERNS = (
    re.compile(r"\b(?:describe|it|test)\s*\.\s*(?:skip|todo)\s*\("),
    re.compile(r"\b(?:xdescribe|xit|xtest)\s*\("),
    re.compile(r"@(?:unittest\.)?(?:skip|skipIf|skipUnless)\b"),
    re.compile(r"@pytest\.mark\.(?:skip|skipif|xfail)\b"),
    re.compile(r"\b(?:pytest\.skip|self\.skipTest)\s*\("),
    re.compile(r"\bt\.Skip(?:Now|f)?\s*\("),
    re.compile(r"#\s*\[\s*ignore(?:\s*=|\s*\])"),
    re.compile(r"@(?:Disabled|Ignore)\b"),
)
FOCUS_PATTERNS = (
    re.compile(r"\b(?:describe|it|test)\s*\.\s*only\s*\("),
    re.compile(r"\b(?:fdescribe|fit|ftest)\s*\("),
)
COVERAGE_EXCLUSION_PATTERNS = (
    re.compile(r"#\s*pragma:\s*no\s*cover", re.IGNORECASE),
    re.compile(r"(?:istanbul|c8)\s+ignore", re.IGNORECASE),
    re.compile(r"sonar\.coverage\.exclusions", re.IGNORECASE),
    re.compile(r"coveragePathIgnorePatterns", re.IGNORECASE),
)
ACK_MARKER_RE = re.compile(r"unskip:\s*allow", re.IGNORECASE)
ACK_RE = re.compile(
    r"unskip:\s*allow\s+([a-z0-9][a-z0-9-]*|\*)(?:@([^\s]+))?\s+--\s+(.+?)\s*$",
    re.IGNORECASE,
)


def _changed_lines(hunk: Hunk, kind: str) -> List[DiffLine]:
    return [line for line in hunk.lines if line.kind == kind]


def _evidence(line: str) -> str:
    compact = line.strip().replace("\t", "    ")
    return compact if len(compact) <= 220 else compact[:217] + "..."


def _finding(
    rule_id: str,
    severity: Severity,
    file: FileDiff,
    hunk_index: int,
    line: Optional[DiffLine],
    message: str,
    suggestion: str,
    evidence: Optional[str] = None,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        path=file.path,
        old_line=line.old_line if line else None,
        new_line=line.new_line if line else None,
        message=message,
        suggestion=suggestion,
        evidence=_evidence(
            evidence if evidence is not None else (line.text if line else file.path)
        ),
        hunk_index=hunk_index,
    )


def _matches_any(text: str, patterns: Iterable[re.Pattern]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _is_assertion_line(text: str) -> bool:
    stripped = text.lstrip()
    if stripped.startswith(("#", "//", "/*", "*")):
        return False
    return bool(ASSERTION_RE.search(text))


def _similar_without_numbers(left: str, right: str) -> float:
    left_clean = re.sub(r"[-+]?\d+(?:\.\d+)?", "#", left.lower())
    right_clean = re.sub(r"[-+]?\d+(?:\.\d+)?", "#", right.lower())
    return difflib.SequenceMatcher(None, left_clean, right_clean).ratio()


def _numbers(text: str) -> List[float]:
    result: List[float] = []
    for raw in re.findall(r"(?<![\w.])[-+]?\d+(?:\.\d+)?", text):
        try:
            result.append(float(raw))
        except ValueError:
            continue
    return result


def _numeric_change(
    removed: Sequence[DiffLine], added: Sequence[DiffLine], keywords: re.Pattern
) -> List[Tuple[DiffLine, DiffLine, float, float]]:
    changes: List[Tuple[DiffLine, DiffLine, float, float]] = []
    used: set = set()
    for old in removed:
        if not keywords.search(old.text):
            continue
        old_values = _numbers(old.text)
        if not old_values:
            continue
        best: Optional[Tuple[float, int, DiffLine]] = None
        for index, new in enumerate(added):
            if index in used or not keywords.search(new.text):
                continue
            new_values = _numbers(new.text)
            if not new_values:
                continue
            similarity = _similar_without_numbers(old.text, new.text)
            if best is None or similarity > best[0]:
                best = (similarity, index, new)
        if best is None or best[0] < 0.58:
            continue
        new_values = _numbers(best[2].text)
        pair_count = min(len(old_values), len(new_values))
        for pos in range(pair_count):
            if old_values[pos] != new_values[pos]:
                changes.append((old, best[2], old_values[pos], new_values[pos]))
                used.add(best[1])
                break
    return changes


def _scan_file(file: FileDiff) -> List[Finding]:
    findings: List[Finding] = []
    path = file.path

    if file.status == "deleted" and is_test_path(file.old_path):
        findings.append(
            _finding(
                "test-file-deleted",
                Severity.HIGH,
                file,
                -1,
                None,
                "A test file is deleted by this diff.",
                "Restore it or use a path-targeted inline acknowledgement from another changed file.",
            )
        )

    if is_snapshot_path(path) and any(file.hunks):
        first = next(
            (line for h in file.hunks for line in h.lines if line.kind == "add"), None
        )
        findings.append(
            _finding(
                "snapshot-changed",
                Severity.LOW,
                file,
                0,
                first,
                "A snapshot or golden file changed.",
                "Review the rendered behavior, not only the regenerated snapshot.",
            )
        )

    for hunk_index, hunk in enumerate(file.hunks):
        added = _changed_lines(hunk, "add")
        removed = _changed_lines(hunk, "remove")

        for line in added:
            if (is_test_path(path) or is_code_path(path)) and _matches_any(
                line.text, SKIP_PATTERNS
            ):
                findings.append(
                    _finding(
                        "skip-added",
                        Severity.HIGH,
                        file,
                        hunk_index,
                        line,
                        "A test skip, ignore, todo, or expected-failure marker was added.",
                        "Keep the test active, or add a same-hunk acknowledgement with an issue-backed reason.",
                    )
                )
            if (is_test_path(path) or is_code_path(path)) and _matches_any(
                line.text, FOCUS_PATTERNS
            ):
                findings.append(
                    _finding(
                        "focus-added",
                        Severity.HIGH,
                        file,
                        hunk_index,
                        line,
                        "A focused test marker was added, which can exclude the rest of the suite.",
                        "Remove the focus marker before merge.",
                    )
                )
            if is_code_path(path) and _matches_any(
                line.text, COVERAGE_EXCLUSION_PATTERNS
            ):
                findings.append(
                    _finding(
                        "coverage-exclusion-added",
                        Severity.MEDIUM,
                        file,
                        hunk_index,
                        line,
                        "A coverage exclusion was added.",
                        "Confirm the excluded code is genuinely untestable and acknowledge it if intentional.",
                    )
                )

        if is_test_path(path):
            removed_assertions = [
                line for line in removed if _is_assertion_line(line.text)
            ]
            added_assertions = [line for line in added if _is_assertion_line(line.text)]
            if len(removed_assertions) > len(added_assertions):
                delta = len(removed_assertions) - len(added_assertions)
                findings.append(
                    _finding(
                        "assertion-count-dropped",
                        Severity.MEDIUM,
                        file,
                        hunk_index,
                        removed_assertions[0],
                        "This hunk removes {} more assertion line{} than it adds.".format(
                            delta, "" if delta == 1 else "s"
                        ),
                        "Verify that the test still checks the original behavior; this count is a review signal, not proof.",
                    )
                )

            removed_normalized = {
                re.sub(r"\s+", "", line.text): line for line in removed
            }
            for line in added:
                uncommented = re.sub(r"^\s*(?://|#|/\*+|\*)\s*", "", line.text)
                key = re.sub(r"\s+", "", uncommented.rstrip("*/ "))
                if ASSERTION_RE.search(uncommented) and key in removed_normalized:
                    findings.append(
                        _finding(
                            "assertion-commented-out",
                            Severity.HIGH,
                            file,
                            hunk_index,
                            line,
                            "An existing assertion appears to have been commented out.",
                            "Restore the assertion or explain the behavior change explicitly.",
                        )
                    )

            matcher_pairs = (
                (
                    "tostrictequal",
                    ("toequal", "tomatchobject", "tobetruthy", "tobedefined"),
                ),
                ("toequal", ("tomatchobject", "tobetruthy", "tobedefined")),
                ("tobe", ("tobetruthy", "tobedefined")),
                ("assertequal", ("asserttrue", "assertisnotnone")),
                ("assertequals", ("asserttrue", "assertnotnull")),
                ("assert_eq!", ("assert!",)),
            )
            for old in removed:
                if not _is_assertion_line(old.text):
                    continue
                old_lower = old.text.lower().replace(" ", "")
                for new in added:
                    if not _is_assertion_line(new.text):
                        continue
                    if (
                        difflib.SequenceMatcher(
                            None, old_lower, new.text.lower().replace(" ", "")
                        ).ratio()
                        < 0.35
                    ):
                        continue
                    new_lower = new.text.lower().replace(" ", "")
                    matched = any(
                        strong in old_lower
                        and any(weak in new_lower for weak in weakers)
                        for strong, weakers in matcher_pairs
                    )
                    if matched:
                        findings.append(
                            _finding(
                                "matcher-weakened",
                                Severity.MEDIUM,
                                file,
                                hunk_index,
                                new,
                                "A specific assertion matcher appears to have been replaced by a weaker one.",
                                "Confirm the new matcher still pins the intended behavior.",
                                "{}  ->  {}".format(
                                    _evidence(old.text), _evidence(new.text)
                                ),
                            )
                        )
                        break

            timeout_keywords = re.compile(r"\b(?:timeout|wait|sleep)\b", re.IGNORECASE)
            for old, new, before, after in _numeric_change(
                removed, added, timeout_keywords
            ):
                if after > before:
                    findings.append(
                        _finding(
                            "timeout-increased",
                            Severity.MEDIUM,
                            file,
                            hunk_index,
                            new,
                            "A test timeout or wait value increased from {} to {}.".format(
                                before, after
                            ),
                            "Confirm this fixes real timing behavior rather than hiding a regression.",
                        )
                    )

            tolerance_keywords = re.compile(
                r"\b(?:tolerance|epsilon|delta|abs_tol|rel_tol|margin|within)\b",
                re.IGNORECASE,
            )
            for old, new, before, after in _numeric_change(
                removed, added, tolerance_keywords
            ):
                if after > before:
                    findings.append(
                        _finding(
                            "tolerance-widened",
                            Severity.MEDIUM,
                            file,
                            hunk_index,
                            new,
                            "A numeric tolerance increased from {} to {}.".format(
                                before, after
                            ),
                            "Verify the wider tolerance is justified by the requirement.",
                        )
                    )

            precision = re.compile(r"toBeCloseTo\s*\([^,]+,\s*(\d+)\s*\)")
            for old in removed:
                old_match = precision.search(old.text)
                if not old_match:
                    continue
                for new in added:
                    new_match = precision.search(new.text)
                    if new_match and int(new_match.group(1)) < int(old_match.group(1)):
                        findings.append(
                            _finding(
                                "tolerance-widened",
                                Severity.MEDIUM,
                                file,
                                hunk_index,
                                new,
                                "toBeCloseTo precision decreased from {} to {} digits.".format(
                                    old_match.group(1), new_match.group(1)
                                ),
                                "Verify the lower precision is required by the specification.",
                            )
                        )
                        break

        if is_coverage_path(path) or is_ci_path(path):
            coverage_keywords = re.compile(
                r"(?:coverage|threshold|fail[_-]?under|min(?:imum)?[_-]?coverage)",
                re.IGNORECASE,
            )
            for old, new, before, after in _numeric_change(
                removed, added, coverage_keywords
            ):
                if after < before:
                    findings.append(
                        _finding(
                            "coverage-threshold-lowered",
                            Severity.HIGH,
                            file,
                            hunk_index,
                            new,
                            "A coverage-related threshold decreased from {} to {}.".format(
                                before, after
                            ),
                            "Restore the threshold or acknowledge the policy change with a concrete reason.",
                        )
                    )

        if is_command_config_path(path):
            for line in added:
                lower = line.text.lower()
                masks_failure = bool(
                    re.search(r"\bcontinue-on-error\s*:\s*true\b", lower)
                    or re.search(r"\ballow_failure\s*:\s*true\b", lower)
                    or (
                        "|| true" in lower
                        and re.search(
                            r"\b(test|pytest|jest|vitest|rspec|go test|cargo test|gradle test|mvn test)\b",
                            lower,
                        )
                    )
                    or ("set +e" in lower and is_ci_path(path))
                )
                if masks_failure:
                    findings.append(
                        _finding(
                            "failure-mask-added",
                            Severity.HIGH,
                            file,
                            hunk_index,
                            line,
                            "This change can let a test or CI failure exit successfully.",
                            "Keep failures blocking, or acknowledge the exception with an issue-backed reason.",
                        )
                    )

    return findings


def _acknowledge(file: FileDiff, findings: List[Finding]) -> List[Finding]:
    for hunk_index, hunk in enumerate(file.hunks):
        valid: Dict[str, str] = {}
        for line in _changed_lines(hunk, "add"):
            if not ACK_MARKER_RE.search(line.text):
                continue
            match = ACK_RE.search(line.text)
            if not match:
                findings.append(
                    _finding(
                        "invalid-acknowledgement",
                        Severity.MEDIUM,
                        file,
                        hunk_index,
                        line,
                        "An Unskip acknowledgement is missing a rule id or concrete reason.",
                        "Use: unskip: allow RULE_ID -- concrete reason",
                    )
                )
                continue
            target_path = match.group(2)
            if target_path is None:
                valid[match.group(1).lower()] = match.group(3).strip()
        for finding in findings:
            if finding.path != file.path or finding.hunk_index != hunk_index:
                continue
            reason = valid.get(finding.rule_id) or valid.get("*")
            if reason and finding.rule_id != "invalid-acknowledgement":
                finding.acknowledged = True
                finding.acknowledgement_reason = reason
    return findings


def _apply_targeted_acknowledgements(
    files: Sequence[FileDiff], findings: List[Finding]
) -> None:
    targeted: List[Tuple[str, str, str]] = []
    for file in files:
        for hunk in file.hunks:
            for line in _changed_lines(hunk, "add"):
                match = ACK_RE.search(line.text)
                if not match or match.group(2) is None:
                    continue
                targeted.append(
                    (
                        match.group(1).lower(),
                        normalized(match.group(2)),
                        match.group(3).strip(),
                    )
                )
    for finding in findings:
        for rule_id, path, reason in targeted:
            if path == normalized(finding.path) and rule_id in {"*", finding.rule_id}:
                finding.acknowledged = True
                finding.acknowledgement_reason = reason
                break


def analyze(
    files: Sequence[FileDiff], source: str, warnings: Optional[List[str]] = None
) -> ScanResult:
    findings: List[Finding] = []
    for file in files:
        file_findings = _scan_file(file)
        findings.extend(_acknowledge(file, file_findings))
    _apply_targeted_acknowledgements(files, findings)
    findings.sort(
        key=lambda item: (
            item.path,
            item.new_line if item.new_line is not None else 10**12,
            item.old_line if item.old_line is not None else 10**12,
            -int(item.severity),
            item.rule_id,
        )
    )
    return ScanResult(
        source=source,
        files_scanned=len(files),
        findings=findings,
        warnings=list(warnings or []),
    )
