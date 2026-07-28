"""v2 reader and validator."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from ._storage import Storage, StorageError, open_storage
from .errors import ClosedExportError, InvalidExportError, UnsupportedVersionError
from .models import (
    Animal,
    BrainRegion,
    ExportLimits,
    ExportMetadata,
    Image,
    Manifest,
    Module,
    ProjectMetadata,
    Slice,
    Staining,
    ValidationIssue,
    ValidationReport,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

_REQUIRED = (
    "manifest.json",
    "project/export.json",
    "project/project.json",
    "project/stainings.json",
    "project/animals.json",
    "project/slices.json",
    "project/brain-regions.json",
)


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


def _parse_model(
    model: type[ModelT],
    value: Any | None,
    path: str,
    issues: list[ValidationIssue],
) -> ModelT | None:
    if value is None:
        return None
    try:
        return model.model_validate(value)
    except ValidationError as error:
        _validation_issues(error, path, issues)
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
) -> None:
    for detail in error.errors(include_url=False):
        field = ".".join(str(item) for item in detail["loc"]) or None
        code = (
            "unsupported_version"
            if field == "exportVersion" and detail["type"] == "literal_error"
            else "invalid_field"
        )
        issues.append(_issue(path, code, detail["msg"], field))


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _cross_validate(
    manifest: Manifest | None,
    metadata: ExportMetadata | None,
    stainings: tuple[Staining, ...] | None,
    animals: tuple[Animal, ...] | None,
    slices: tuple[Slice, ...] | None,
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
    for path, name, values in (
        (
            "project/stainings.json",
            "staining ID",
            [item.id for item in stainings or ()],
        ),
        ("project/animals.json", "animal ID", [item.id for item in animals or ()]),
        ("project/slices.json", "slice ID", [item.id for item in slices or ()]),
    ):
        for duplicate in _duplicates(values):
            issues.append(
                _issue(path, "duplicate_id", f"duplicate {name}: {duplicate}")
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


def _validate_data(
    storage: Storage,
    slices: tuple[Slice, ...],
    stainings: tuple[Staining, ...],
    limits: ExportLimits,
    issues: list[ValidationIssue],
) -> None:
    staining_ids = {staining.id for staining in stainings}
    image_ids: list[str] = []
    archive_paths: list[str] = []
    for slice_ in slices:
        base = f"data/slices/{slice_.id}"
        slice_path = f"{base}/slice.json"
        slice_record = _parse_model(
            Slice,
            _read_json(storage, slice_path, limits, issues),
            slice_path,
            issues,
        )
        images_path = f"{base}/images.json"
        images = _parse_list(
            Image,
            _read_json(storage, images_path, limits, issues),
            images_path,
            issues,
        )
        if slice_record is not None and (
            slice_record.id,
            slice_record.animal_id,
            slice_record.ap_mm,
        ) != (slice_.id, slice_.animal_id, slice_.ap_mm):
            issues.append(
                _issue(
                    slice_path,
                    "inconsistent_slice",
                    "slice metadata does not agree with project/slices.json",
                )
            )
        for index, image in enumerate(images or ()):
            image_ids.append(image.image_id)
            archive_paths.append(image.archive_path)
            sanitized = image.original_filename.replace("/", "_").replace("\\", "_")
            expected = f"{base}/images/{image.image_id}__{sanitized}"
            if image.slice_id != slice_.id:
                issues.append(
                    _issue(
                        images_path,
                        "inconsistent_slice",
                        "image sliceId does not match its directory",
                        f"{index}.sliceId",
                    )
                )
            if image.staining_id not in staining_ids:
                issues.append(
                    _issue(
                        images_path,
                        "unknown_staining",
                        f"image references unknown staining {image.staining_id}",
                        f"{index}.stainingId",
                    )
                )
            if image.archive_path != expected:
                issues.append(
                    _issue(
                        images_path,
                        "invalid_archive_path",
                        f"archivePath must be {expected}",
                        f"{index}.archivePath",
                    )
                )
            elif image.archive_path not in storage.members:
                issues.append(
                    _issue(
                        image.archive_path,
                        "missing_member",
                        "referenced image member is missing",
                    )
                )
    for label, values in (("imageId", image_ids), ("archivePath", archive_paths)):
        for duplicate in _duplicates(values):
            issues.append(
                _issue(
                    "data",
                    "duplicate_image",
                    f"duplicate {label}: {duplicate}",
                    label,
                )
            )


def _validate_registration(
    storage: Storage,
    manifest: Manifest,
    limits: ExportLimits,
    issues: list[ValidationIssue],
) -> None:
    path = "registration/atlas/atlas-manifest.json"
    if manifest.atlas is None:
        return
    value = _read_json(storage, path, limits, issues)
    if not isinstance(value, dict):
        return
    for field in ("id", "key", "version", "name", "species", "plane", "spec"):
        if field not in value:
            issues.append(_issue(path, "invalid_field", "field is required", field))
    for field in ("id", "key", "version", "name"):
        if value.get(field) != getattr(manifest.atlas, field):
            issues.append(
                _issue(
                    path,
                    "inconsistent_atlas",
                    f"{field} does not agree with manifest.json",
                    field,
                )
            )


def _validate_classification(
    storage: Storage,
    limits: ExportLimits,
    issues: list[ValidationIssue],
) -> None:
    path = "classification/manifest.json"
    value = _read_json(storage, path, limits, issues)
    if not isinstance(value, dict):
        return
    if value.get("exportVersion") != "v2":
        issues.append(_issue(path, "unsupported_version", "exportVersion must be v2"))
    for collection, path_fields in (
        (
            "stainings",
            (
                "classifierPath",
                "trainingSummaryPath",
                "trainingSamplesPath",
                "resultIndexPath",
            ),
        ),
        ("matches", ("matchPath",)),
    ):
        entries = value.get(collection)
        if not isinstance(entries, list):
            issues.append(
                _issue(
                    path, "invalid_field", f"{collection} must be an array", collection
                )
            )
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                issues.append(
                    _issue(
                        path,
                        "invalid_field",
                        "entry must be an object",
                        f"{collection}.{index}",
                    )
                )
                continue
            for path_field in path_fields:
                member = entry.get(path_field)
                if not isinstance(member, str) or member not in storage.members:
                    issues.append(
                        _issue(
                            path,
                            "invalid_reference",
                            f"{path_field} must name an existing member",
                            f"{collection}.{index}.{path_field}",
                        )
                    )


class ProjectExport:
    """An open, validated NeuroQP project export."""

    def __init__(
        self,
        storage: Storage,
        manifest: Manifest,
        metadata: ExportMetadata,
        project: ProjectMetadata,
        stainings: tuple[Staining, ...],
        animals: tuple[Animal, ...],
        slices: tuple[Slice, ...],
        brain_regions: tuple[BrainRegion, ...],
    ) -> None:
        self._storage = storage
        self._manifest = manifest
        self._metadata = metadata
        self._project = project
        self._stainings = stainings
        self._animals = animals
        self._slices = slices
        self._brain_regions = brain_regions
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise ClosedExportError("export is closed")

    @property
    def closed(self) -> bool:
        """Whether this export has been closed."""

        return self._closed

    @property
    def manifest(self) -> Manifest:
        """Root manifest."""

        self._ensure_open()
        return self._manifest

    @property
    def metadata(self) -> ExportMetadata:
        """Export metadata."""

        self._ensure_open()
        return self._metadata

    @property
    def project(self) -> ProjectMetadata:
        """Project metadata."""

        self._ensure_open()
        return self._project

    @property
    def stainings(self) -> tuple[Staining, ...]:
        """Project stainings."""

        self._ensure_open()
        return self._stainings

    @property
    def animals(self) -> tuple[Animal, ...]:
        """Project animals."""

        self._ensure_open()
        return self._animals

    @property
    def slices(self) -> tuple[Slice, ...]:
        """Project slices."""

        self._ensure_open()
        return self._slices

    @property
    def brain_regions(self) -> tuple[BrainRegion, ...]:
        """Selected project brain regions."""

        self._ensure_open()
        return self._brain_regions

    @property
    def id(self) -> str:
        """Project ID."""

        return self.manifest.project.id

    @property
    def version(self) -> str:
        """Wire export version."""

        return self.manifest.export_version

    @property
    def exported_at(self) -> datetime:
        """Export timestamp."""

        return self.manifest.exported_at

    @property
    def name(self) -> str:
        """Project name."""

        return self.project.name

    def close(self) -> None:
        """Close the export. Repeated calls are safe."""

        if not self._closed:
            self._storage.close()
            self._closed = True

    def __enter__(self) -> ProjectExport:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _load(
    source: str | Path,
    limits: ExportLimits,
) -> tuple[ProjectExport | None, ValidationReport]:
    issues: list[ValidationIssue] = []
    try:
        storage = open_storage(Path(source), limits)
    except StorageError as error:
        return None, ValidationReport(issues=tuple(error.issues))

    for path in _REQUIRED:
        if path not in storage.members:
            issues.append(_issue(path, "missing_member", "required member is missing"))

    values = {
        path: _read_json(storage, path, limits, issues)
        for path in _REQUIRED
        if path in storage.members
    }
    manifest = _parse_model(
        Manifest, values.get("manifest.json"), "manifest.json", issues
    )
    metadata = _parse_model(
        ExportMetadata,
        values.get("project/export.json"),
        "project/export.json",
        issues,
    )
    project = _parse_model(
        ProjectMetadata,
        values.get("project/project.json"),
        "project/project.json",
        issues,
    )
    stainings = _parse_list(
        Staining,
        values.get("project/stainings.json"),
        "project/stainings.json",
        issues,
    )
    animals = _parse_list(
        Animal,
        values.get("project/animals.json"),
        "project/animals.json",
        issues,
    )
    slices = _parse_list(
        Slice,
        values.get("project/slices.json"),
        "project/slices.json",
        issues,
    )
    brain_regions = _parse_list(
        BrainRegion,
        values.get("project/brain-regions.json"),
        "project/brain-regions.json",
        issues,
    )

    _cross_validate(manifest, metadata, stainings, animals, slices, issues)
    if (
        manifest is not None
        and Module.DATA in manifest.included_modules
        and slices is not None
        and stainings is not None
    ):
        _validate_data(storage, slices, stainings, limits, issues)
    if manifest is not None and Module.REGISTRATION in manifest.included_modules:
        _validate_registration(storage, manifest, limits, issues)
    if manifest is not None and Module.CLASSIFICATION in manifest.included_modules:
        _validate_classification(storage, limits, issues)

    report = ValidationReport(issues=tuple(issues))
    if not report.valid:
        storage.close()
        return None, report
    assert manifest is not None
    assert metadata is not None
    assert project is not None
    assert stainings is not None
    assert animals is not None
    assert slices is not None
    assert brain_regions is not None
    return (
        ProjectExport(
            storage,
            manifest,
            metadata,
            project,
            stainings,
            animals,
            slices,
            brain_regions,
        ),
        report,
    )


def validate_export(
    source: str | Path,
    *,
    limits: ExportLimits | None = None,
) -> ValidationReport:
    """Validate a local v2 ZIP or extracted directory."""

    export, report = _load(source, limits or ExportLimits())
    if export is not None:
        export.close()
    return report


def open_export(
    source: str | Path,
    *,
    limits: ExportLimits | None = None,
) -> ProjectExport:
    """Open and validate a local v2 ZIP or extracted directory."""

    export, report = _load(source, limits or ExportLimits())
    if export is not None:
        return export
    error_type = (
        UnsupportedVersionError
        if any(issue.code == "unsupported_version" for issue in report.issues)
        else InvalidExportError
    )
    raise error_type(report)
