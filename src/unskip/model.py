from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, value: str) -> "Severity":
        return {
            "low": cls.LOW,
            "medium": cls.MEDIUM,
            "high": cls.HIGH,
        }[value]


@dataclass
class DiffLine:
    kind: str
    text: str
    old_line: Optional[int]
    new_line: Optional[int]


@dataclass
class Hunk:
    old_start: int
    new_start: int
    header: str
    lines: List[DiffLine] = field(default_factory=list)


@dataclass
class FileDiff:
    old_path: str
    new_path: str
    status: str = "modified"
    hunks: List[Hunk] = field(default_factory=list)
    binary: bool = False

    @property
    def path(self) -> str:
        return self.old_path if self.status == "deleted" else self.new_path


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    path: str
    message: str
    suggestion: str
    evidence: str
    hunk_index: int
    old_line: Optional[int] = None
    new_line: Optional[int] = None
    acknowledged: bool = False
    acknowledgement_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.label,
            "path": self.path,
            "old_line": self.old_line,
            "new_line": self.new_line,
            "message": self.message,
            "suggestion": self.suggestion,
            "evidence": self.evidence,
            "acknowledged": self.acknowledged,
            "acknowledgement_reason": self.acknowledgement_reason,
        }


@dataclass
class ScanResult:
    source: str
    files_scanned: int
    findings: List[Finding]
    warnings: List[str] = field(default_factory=list)

    def counts(self) -> Dict[str, int]:
        counts = {"high": 0, "medium": 0, "low": 0, "acknowledged": 0}
        for finding in self.findings:
            if finding.acknowledged:
                counts["acknowledged"] += 1
            else:
                counts[finding.severity.label] += 1
        counts["total"] = len(self.findings)
        counts["unacknowledged"] = len(self.findings) - counts["acknowledged"]
        return counts
