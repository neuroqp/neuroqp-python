"""Command-line interface."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ._project import ProjectExport
from ._reader import open_export, validate_export
from .errors import InvalidExportError
from .models import Module, ValidationReport


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


def _print_issues(report: ValidationReport) -> None:
    for issue in report.issues:
        field = f" [{issue.field}]" if issue.field else ""
        print(f"- {issue.path}{field}: {issue.message} ({issue.code})")


def _inspection_payload(export: ProjectExport, source: Path) -> dict[str, object]:
    atlas = export.manifest.atlas
    return {
        "valid": True,
        "source": str(source),
        "exportVersion": export.version,
        "exportId": export.metadata.export_id,
        "exportedAt": export.exported_at.isoformat(),
        "expiresAt": export.metadata.expires_at.isoformat(),
        "project": {
            "id": export.id,
            "name": export.name,
            "type": export.project.type,
            "atlasId": export.project.atlas_id,
            "comments": export.project.comments,
            "wholeSlice": {
                "label": export.project.whole_slice_label,
                "micronsPerPixel": export.project.whole_slice_microns_per_pixel,
            },
            "detailImage": {
                "label": export.project.detail_image_label,
                "micronsPerPixel": export.project.detail_microns_per_pixel,
            },
        },
        "atlas": (
            {
                "id": atlas.id,
                "key": atlas.key,
                "version": atlas.version,
                "name": atlas.name,
            }
            if atlas
            else None
        ),
        "modules": [module.value for module in export.manifest.included_modules],
        "counts": {
            "animals": len(export.animals),
            "slices": len(export.slices),
            "stainings": len(export.stainings),
            "brainRegions": len(export.brain_regions),
        },
        "animals": [{"id": item.id, "name": item.name} for item in export.animals],
        "stainings": [{"id": item.id, "name": item.name} for item in export.stainings],
        "brainRegions": [
            {
                "structureId": item.structure_id,
                "name": item.name,
                "acronym": item.acronym,
            }
            for item in export.brain_regions
        ],
        "selectedClassifierHeadIdsByStaining": (
            export.manifest.selected_classifier_head_ids_by_staining
        ),
        "linkedTrainingRunIdsByStaining": (
            export.manifest.linked_training_run_ids_by_staining
        ),
    }


def _print_collection(label: str, items: list[str]) -> None:
    print(f"  {label}: {len(items)}")
    for item in items:
        print(f"    - {item}")


def _print_inspection(export: ProjectExport, source: Path) -> None:
    project = export.project
    atlas = export.manifest.atlas
    included_modules = set(export.manifest.included_modules)

    print("Validation")
    print("  Status: valid")
    print(f"  Source: {source}")

    print("\nExport")
    print(f"  Format: {export.version}")
    print(f"  ID: {export.metadata.export_id}")
    print(f"  Exported: {export.exported_at.isoformat()}")
    print(f"  Expires: {export.metadata.expires_at.isoformat()}")

    print("\nProject")
    print(f"  Name: {export.name}")
    print(f"  ID: {export.id}")
    print(f"  Type: {project.type}")
    print(
        f"  Whole-slice image: {project.whole_slice_label} "
        f"({project.whole_slice_microns_per_pixel:g} µm/pixel)"
    )
    print(
        f"  Detail image: {project.detail_image_label} "
        f"({project.detail_microns_per_pixel:g} µm/pixel)"
    )
    if project.comments:
        print(f"  Comments: {project.comments}")

    print("\nModules")
    for module in Module:
        status = "included" if module in included_modules else "not included"
        print(f"  {module.value}: {status}")

    print("\nAtlas")
    if atlas:
        print(f"  Name: {atlas.name}")
        print(f"  ID: {atlas.id}")
        print(f"  Key: {atlas.key}")
        print(f"  Version: {atlas.version}")
    else:
        print("  None")

    print("\nContents")
    _print_collection(
        "Animals",
        [f"{item.name} ({item.id})" for item in export.animals],
    )
    print(f"  Slices: {len(export.slices)}")
    _print_collection(
        "Stainings",
        [f"{item.name} ({item.id})" for item in export.stainings],
    )
    _print_collection(
        "Brain regions",
        [
            f"{item.name} ({item.acronym}, {item.structure_id})"
            for item in export.brain_regions
        ],
    )

    print("\nClassifier selections")
    staining_names = {item.id: item.name for item in export.stainings}
    selections = export.manifest.selected_classifier_head_ids_by_staining
    if selections:
        for staining_id, classifier_id in selections.items():
            staining = staining_names.get(staining_id, staining_id)
            print(f"  {staining}: {classifier_id}")
    else:
        print("  None")


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
            _print_issues(report)
        return 0 if report.valid else 1

    try:
        with open_export(args.export) as export:
            if args.as_json:
                print(
                    json.dumps(_inspection_payload(export, args.export), sort_keys=True)
                )
            else:
                _print_inspection(export, args.export)
    except InvalidExportError as error:
        payload = _report_payload(error.report)
        if args.as_json:
            print(json.dumps(payload, sort_keys=True))
        else:
            print(f"Cannot inspect invalid export: {args.export}")
            _print_issues(error.report)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
