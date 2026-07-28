"""Command-line interface."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ._reader import open_export, validate_export
from .errors import InvalidExportError
from .models import ValidationReport


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="neuroqp")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("validate", "validate a NeuroQP export"),
        ("inspect", "inspect project metadata"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("export", type=Path)
        command.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _report_payload(report: ValidationReport) -> dict[str, object]:
    issues = report.issues
    return {
        "valid": not issues,
        "issues": [issue.model_dump(mode="json") for issue in issues],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the NeuroQP CLI."""

    args = _parser().parse_args(argv)
    if args.command == "validate":
        report = validate_export(args.export)
        payload = _report_payload(report)
        if args.as_json:
            print(json.dumps(payload, sort_keys=True))
        elif report.valid:
            print(f"Valid NeuroQP v2 export: {args.export}")
        else:
            print(f"Invalid NeuroQP export: {args.export}")
            for issue in report.issues:
                field = f" [{issue.field}]" if issue.field else ""
                print(f"- {issue.path}{field}: {issue.message} ({issue.code})")
        return 0 if report.valid else 1

    try:
        with open_export(args.export) as export:
            payload = {
                "exportVersion": export.version,
                "exportId": export.metadata.export_id,
                "exportedAt": export.exported_at.isoformat(),
                "project": {
                    "id": export.id,
                    "name": export.name,
                    "type": export.project.type,
                },
                "modules": [
                    module.value for module in export.manifest.included_modules
                ],
                "counts": {
                    "animals": len(export.animals),
                    "slices": len(export.slices),
                    "stainings": len(export.stainings),
                    "brainRegions": len(export.brain_regions),
                },
            }
    except InvalidExportError as error:
        payload = _report_payload(error.report)
        if args.as_json:
            print(json.dumps(payload, sort_keys=True))
        else:
            print(f"Cannot inspect invalid export: {args.export}")
        return 1
    if args.as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        project = payload["project"]
        counts = payload["counts"]
        assert isinstance(project, dict)
        assert isinstance(counts, dict)
        print(f"{project['name']} ({project['id']})")
        print(f"Export: {payload['exportVersion']} · {payload['exportedAt']}")
        print(
            f"Animals: {counts['animals']} · Slices: {counts['slices']} · "
            f"Stainings: {counts['stainings']} · "
            f"Brain regions: {counts['brainRegions']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
