from __future__ import annotations

import json
from collections import defaultdict
from typing import Dict, List

from . import __version__
from .model import Finding, ScanResult, Severity


def _visible(result: ScanResult, show_acknowledged: bool) -> List[Finding]:
    return [
        finding
        for finding in result.findings
        if show_acknowledged or not finding.acknowledged
    ]


def render_text(result: ScanResult, show_acknowledged: bool = False) -> str:
    counts = result.counts()
    visible = _visible(result, show_acknowledged)
    lines: List[str] = []
    if counts["unacknowledged"] == 0:
        lines.append(
            "Unskip: no unacknowledged test-weakening signals in {} changed file{}.".format(
                result.files_scanned, "" if result.files_scanned == 1 else "s"
            )
        )
    else:
        lines.append(
            "Unskip found {} unacknowledged signal{} ({} high, {} medium, {} low) in {} changed file{}.".format(
                counts["unacknowledged"],
                "" if counts["unacknowledged"] == 1 else "s",
                counts["high"],
                counts["medium"],
                counts["low"],
                result.files_scanned,
                "" if result.files_scanned == 1 else "s",
            )
        )

    grouped: Dict[str, List[Finding]] = defaultdict(list)
    for finding in visible:
        grouped[finding.path].append(finding)
    for path in sorted(grouped):
        lines.extend(["", path])
        for finding in grouped[path]:
            line = finding.new_line or finding.old_line
            location = "L{}".format(line) if line is not None else "file"
            state = " acknowledged" if finding.acknowledged else ""
            lines.append(
                "  {} {}{} {}  [{}]".format(
                    location,
                    finding.severity.label.upper(),
                    state,
                    finding.message,
                    finding.rule_id,
                )
            )
            if finding.evidence:
                lines.append("    evidence: {}".format(finding.evidence))
            if finding.acknowledged:
                lines.append("    reason: {}".format(finding.acknowledgement_reason))
            else:
                lines.append("    review: {}".format(finding.suggestion))

    if counts["acknowledged"] and not show_acknowledged:
        lines.extend(
            [
                "",
                "{} acknowledged signal{} hidden; use --show-acknowledged to display {}.".format(
                    counts["acknowledged"],
                    "" if counts["acknowledged"] == 1 else "s",
                    "it" if counts["acknowledged"] == 1 else "them",
                ),
            ]
        )
    for warning in result.warnings:
        lines.append("warning: {}".format(warning))
    lines.extend(
        ["", "Signals are review prompts, not proof of cheating or correctness."]
    )
    return "\n".join(lines)


def render_json(result: ScanResult) -> str:
    payload = {
        "tool": "unskip",
        "version": __version__,
        "source": result.source,
        "summary": {"files_scanned": result.files_scanned, **result.counts()},
        "warnings": result.warnings,
        "findings": [finding.to_dict() for finding in result.findings],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _escape_command(value: str, property_value: bool = False) -> str:
    value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if property_value:
        value = value.replace(":", "%3A").replace(",", "%2C")
    return value


def render_github(result: ScanResult, show_acknowledged: bool = False) -> str:
    lines: List[str] = []
    for finding in _visible(result, show_acknowledged):
        level = {
            Severity.HIGH: "error",
            Severity.MEDIUM: "warning",
            Severity.LOW: "notice",
        }[finding.severity]
        if finding.acknowledged:
            level = "notice"
        properties = [
            "file={}".format(_escape_command(finding.path, True)),
            "title={}".format(
                _escape_command("unskip/{}".format(finding.rule_id), True)
            ),
        ]
        line = finding.new_line or finding.old_line
        if line is not None:
            properties.append("line={}".format(line))
        message = finding.message
        if finding.acknowledged:
            message += " Acknowledged: {}".format(finding.acknowledgement_reason)
        lines.append(
            "::{} {}::{}".format(level, ",".join(properties), _escape_command(message))
        )
    counts = result.counts()
    lines.append(
        "Unskip: {} unacknowledged, {} acknowledged across {} changed files.".format(
            counts["unacknowledged"], counts["acknowledged"], result.files_scanned
        )
    )
    return "\n".join(lines)


def should_fail(result: ScanResult, threshold: str) -> bool:
    if threshold == "never":
        return False
    minimum = Severity.parse(threshold)
    return any(
        not finding.acknowledged and finding.severity >= minimum
        for finding in result.findings
    )
