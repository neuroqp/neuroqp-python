"""Shared v2 metadata parsing and validation helpers."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from ._storage import Storage, StorageError
from .models import (
    Animal,
    BrainRegion,
    ExportLimits,
    ExportMetadata,
    Manifest,
    ProjectMetadata,
    Slice,
    Staining,
    ValidationIssue,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _issue(
    path: str,
    code: str,
    message: str,
    field: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(path=path, field=field, code=code, message=message)


def _read_json(
    storage: Storage,
    path: str,
    limits: ExportLimits,
    issues: list[ValidationIssue],
) -> Any | None:
    try:
        data = storage.read(path, limits.max_metadata_bytes)
    except FileNotFoundError:
        issues.append(_issue(path, "missing_member", "required member is missing"))
        return None
    except StorageError as error:
        issues.extend(error.issues)
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as error:
        issues.append(_issue(path, "invalid_utf8", str(error)))
    except json.JSONDecodeError as error:
        issues.append(_issue(path, "invalid_json", error.msg, f"line {error.lineno}"))
    return None


def _read_jsonl(
    model: type[ModelT],
    storage: Storage,
    path: str,
    limits: ExportLimits,
    issues: list[ValidationIssue],
) -> tuple[ModelT, ...] | None:
    try:
        data = storage.read(path, limits.max_metadata_bytes)
    except FileNotFoundError:
        issues.append(_issue(path, "missing_member", "required member is missing"))
        return None
    except StorageError as error:
        issues.extend(error.issues)
        return None
    records: list[ModelT] = []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        issues.append(_issue(path, "invalid_utf8", str(error)))
        return None
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            issues.append(
                _issue(path, "invalid_json", error.msg, f"line {line_number}")
            )
            continue
        record = _parse_model(model, value, path, issues, prefix=f"{line_number}.")
        if record is not None:
            records.append(record)
    return tuple(records)


def _parse_model(
    model: type[ModelT],
    value: Any | None,
    path: str,
    issues: list[ValidationIssue],
    *,
    prefix: str = "",
) -> ModelT | None:
    if value is None:
        return None
    try:
        return model.model_validate(value)
    except ValidationError as error:
        _validation_issues(error, path, issues, prefix)
        return None


def _parse_list(
    model: type[ModelT],
    value: Any | None,
    path: str,
    issues: list[ValidationIssue],
) -> tuple[ModelT, ...] | None:
    if value is None:
        return None
    try:
        return tuple(TypeAdapter(list[model]).validate_python(value))  # type: ignore[valid-type]
    except ValidationError as error:
        _validation_issues(error, path, issues)
        return None


def _validation_issues(
    error: ValidationError,
    path: str,
    issues: list[ValidationIssue],
    prefix: str = "",
) -> None:
    for detail in error.errors(include_url=False):
        field = prefix + ".".join(str(item) for item in detail["loc"])
        code = (
            "unsupported_version"
            if field == "exportVersion" and detail["type"] == "literal_error"
            else "invalid_field"
        )
        issues.append(_issue(path, code, detail["msg"], field or None))


def _duplicates(values: Sequence[str | int]) -> set[str | int]:
    seen: set[str | int] = set()
    duplicates: set[str | int] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _check_duplicates(
    path: str,
    label: str,
    values: Sequence[str | int],
    issues: list[ValidationIssue],
    *,
    code: str = "duplicate_id",
) -> None:
    for duplicate in _duplicates(values):
        issues.append(_issue(path, code, f"duplicate {label}: {duplicate}"))


def _cross_validate(
    manifest: Manifest | None,
    metadata: ExportMetadata | None,
    project: ProjectMetadata | None,
    stainings: tuple[Staining, ...] | None,
    animals: tuple[Animal, ...] | None,
    slices: tuple[Slice, ...] | None,
    brain_regions: tuple[BrainRegion, ...] | None,
    issues: list[ValidationIssue],
) -> None:
    if manifest is not None and manifest.project_metadata_path != "project/export.json":
        issues.append(
            _issue(
                "manifest.json",
                "invalid_reference",
                "projectMetadataPath must be project/export.json",
                "projectMetadataPath",
            )
        )
    if manifest is not None and metadata is not None:
        comparisons = (
            ("exportVersion", manifest.export_version, metadata.export_version),
            ("exportedAt", manifest.exported_at, metadata.exported_at),
            ("exportId", manifest.export_id, metadata.export_id),
            ("projectId", manifest.project.id, metadata.project_id),
            (
                "requestedModules",
                set(manifest.included_modules),
                set(metadata.requested_modules),
            ),
            (
                "selectedClassifierHeadIdsByStaining",
                manifest.selected_classifier_head_ids_by_staining,
                metadata.selected_classifier_head_ids_by_staining,
            ),
        )
        for field, root_value, metadata_value in comparisons:
            if root_value != metadata_value:
                issues.append(
                    _issue(
                        "project/export.json",
                        "inconsistent_reference",
                        f"{field} does not agree with manifest.json",
                        field,
                    )
                )
    collections = (
        (
            "project/stainings.json",
            "staining ID",
            [item.id for item in stainings or ()],
        ),
        (
            "project/animals.json",
            "animal ID",
            [item.id for item in animals or ()],
        ),
        (
            "project/slices.json",
            "slice ID",
            [item.id for item in slices or ()],
        ),
        (
            "project/brain-regions.json",
            "structure ID",
            [item.structure_id for item in brain_regions or ()],
        ),
    )
    for path, label, values in collections:
        _check_duplicates(path, label, values, issues)
    _check_duplicates(
        "project/stainings.json",
        "staining name",
        [item.name for item in stainings or ()],
        issues,
        code="duplicate_name",
    )
    _check_duplicates(
        "project/animals.json",
        "animal name",
        [item.name for item in animals or ()],
        issues,
        code="duplicate_name",
    )
    animal_ids = {animal.id for animal in animals or ()}
    for index, slice_ in enumerate(slices or ()):
        if slice_.animal_id not in animal_ids:
            issues.append(
                _issue(
                    "project/slices.json",
                    "unknown_animal",
                    f"slice references unknown animal {slice_.animal_id}",
                    f"{index}.animalId",
                )
            )
    staining_ids = {staining.id for staining in stainings or ()}
    if manifest is not None:
        for staining_id in (
            manifest.selected_classifier_head_ids_by_staining
            | manifest.linked_training_run_ids_by_staining
        ):
            if staining_id not in staining_ids:
                issues.append(
                    _issue(
                        "manifest.json",
                        "unknown_staining",
                        f"selection references unknown staining {staining_id}",
                    )
                )
        if (
            project is not None
            and project.atlas_id is not None
            and (manifest.atlas is None or project.atlas_id != manifest.atlas.id)
        ):
            issues.append(
                _issue(
                    "project/project.json",
                    "inconsistent_atlas",
                    "atlasId does not agree with manifest.json",
                    "atlasId",
                )
            )
