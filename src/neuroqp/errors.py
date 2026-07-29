"""Public NeuroQP exception hierarchy."""

from __future__ import annotations

from .models import ValidationReport


class NeuroQPError(Exception):
    """Base class for SDK errors."""


class InvalidExportError(NeuroQPError):
    """Raised when export metadata fails validation."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        count = len(report.issues)
        message = f"invalid NeuroQP export ({count} issue{'s' if count != 1 else ''})"
        size_issue = next(
            (issue for issue in report.issues if issue.code == "size_limit"),
            None,
        )
        if size_issue is not None:
            message = f"{message}: {size_issue.message}"
        super().__init__(message)


class UnsupportedVersionError(InvalidExportError):
    """Raised when the export wire version is unsupported."""


class ObjectNotFoundError(NeuroQPError, LookupError):
    """Raised when a singular object lookup has no result."""


class AmbiguousNameError(NeuroQPError, LookupError):
    """Raised when a singular name lookup has several results."""


class ClosedExportError(NeuroQPError):
    """Raised when a closed export is accessed."""
