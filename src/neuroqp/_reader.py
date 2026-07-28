"""v2 reader and aggregate metadata validator."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from ._classification import _ClassificationData, _MatchData
from ._classification_reader import _validate_classification
from ._project import ProjectExport
from ._storage import Storage, StorageError, open_storage
from ._validation import (
    _check_duplicates,
    _cross_validate,
    _issue,
    _parse_list,
    _parse_model,
    _read_json,
)
from .errors import InvalidExportError, UnsupportedVersionError
from .models import (
    Animal,
    Atlas,
    AtlasRegistration,
    BrainRegion,
    DetailTransform,
    ExportLimits,
    ExportMetadata,
    Image,
    Manifest,
    Module,
    Point,
    ProjectMetadata,
    RegistrationLandmark,
    Slice,
    Staining,
    ValidationIssue,
    ValidationReport,
)

_REQUIRED = (
    "manifest.json",
    "project/export.json",
    "project/project.json",
    "project/stainings.json",
    "project/animals.json",
    "project/slices.json",
    "project/brain-regions.json",
)


def _validate_data(
    storage: Storage,
    slices: tuple[Slice, ...],
    stainings: tuple[Staining, ...],
    limits: ExportLimits,
    issues: list[ValidationIssue],
) -> tuple[tuple[Slice, ...], dict[str, tuple[Image, ...]]]:
    staining_ids = {staining.id for staining in stainings}
    image_ids: list[str] = []
    archive_paths: list[str] = []
    detailed_slices: list[Slice] = []
    images_by_slice: dict[str, tuple[Image, ...]] = {}
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
        detailed_slices.append(slice_record or slice_)
        images_by_slice[slice_.id] = images or ()
        if slice_record is not None and (
            slice_record.id,
            slice_record.animal_id,
            slice_record.slice_coordinate_mm,
        ) != (slice_.id, slice_.animal_id, slice_.slice_coordinate_mm):
            issues.append(
                _issue(
                    slice_path,
                    "inconsistent_slice",
                    "slice metadata does not agree with project/slices.json",
                )
            )
        for index, image in enumerate(images or ()):
            image_ids.append(image.id)
            archive_paths.append(image.archive_path)
            sanitized = image.original_filename.replace("/", "_").replace("\\", "_")
            expected = f"{base}/images/{image.id}__{sanitized}"
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
        _check_duplicates("data", label, values, issues, code="duplicate_image")
    return tuple(detailed_slices), images_by_slice


def _validate_registration(
    storage: Storage,
    manifest: Manifest,
    slices: tuple[Slice, ...],
    limits: ExportLimits,
    issues: list[ValidationIssue],
) -> tuple[Atlas | None, dict[str, AtlasRegistration], dict[str, DetailTransform]]:
    path = "registration/atlas/atlas-manifest.json"
    value = _read_json(storage, path, limits, issues)
    atlas: Atlas | None = None
    if isinstance(value, dict):
        if manifest.atlas is not None:
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
        normalized = dict(value)
        normalized["specification"] = normalized.pop("spec", None)
        atlas = _parse_model(Atlas, normalized, path, issues)
        if atlas is not None and manifest.atlas is None:
            issues.append(
                _issue(
                    path,
                    "inconsistent_atlas",
                    "registration atlas is absent from manifest.json",
                )
            )
    atlas_registrations: dict[str, AtlasRegistration] = {}
    detail_transforms: dict[str, DetailTransform] = {}
    for slice_ in slices:
        base = f"registration/slices/{slice_.id}"
        registration_path = f"{base}/atlas-registration.json"
        if registration_path in storage.members:
            raw = _read_json(storage, registration_path, limits, issues)
            if isinstance(raw, dict):
                landmarks: list[RegistrationLandmark] = []
                points = raw.get("pointsV2")
                if isinstance(points, list):
                    try:
                        landmarks = [
                            RegistrationLandmark(
                                image=Point(x=point["imageXPx"], y=point["imageYPx"]),
                                atlas_plane_mm=Point(
                                    x=point["atlasPlaneXMm"],
                                    y=point["atlasPlaneYMm"],
                                ),
                            )
                            for point in points
                        ]
                    except (KeyError, TypeError, ValidationError) as error:
                        issues.append(
                            _issue(
                                registration_path,
                                "invalid_field",
                                str(error),
                                "pointsV2",
                            )
                        )
                else:
                    issues.append(
                        _issue(
                            registration_path,
                            "invalid_field",
                            "pointsV2 must be an array",
                            "pointsV2",
                        )
                    )
                if raw.get("slideId") != slice_.id:
                    issues.append(
                        _issue(
                            registration_path,
                            "inconsistent_slice",
                            "slideId does not match its directory",
                            "slideId",
                        )
                    )
                try:
                    atlas_registrations[slice_.id] = AtlasRegistration(
                        slice_id=raw["slideId"],
                        slice_coordinate_mm=raw["apMm"],
                        landmarks=tuple(landmarks),
                    )
                except (KeyError, ValidationError) as error:
                    issues.append(
                        _issue(
                            registration_path,
                            "invalid_field",
                            str(error),
                        )
                    )
        transform_path = f"{base}/detail-to-whole-slice.json"
        if transform_path in storage.members:
            raw = _read_json(storage, transform_path, limits, issues)
            if isinstance(raw, dict):
                if raw.get("slideId") != slice_.id:
                    issues.append(
                        _issue(
                            transform_path,
                            "inconsistent_slice",
                            "slideId does not match its directory",
                            "slideId",
                        )
                    )
                try:
                    detail_transforms[slice_.id] = DetailTransform(
                        slice_id=raw["slideId"],
                        corners=tuple(
                            Point.model_validate(point) for point in raw["corners"]
                        ),
                    )
                except (KeyError, TypeError, ValidationError) as error:
                    issues.append(
                        _issue(transform_path, "invalid_field", str(error), "corners")
                    )
    return atlas, atlas_registrations, detail_transforms


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
    _cross_validate(
        manifest,
        metadata,
        project,
        stainings,
        animals,
        slices,
        brain_regions,
        issues,
    )
    images_by_slice: dict[str, tuple[Image, ...]] = {}
    atlas: Atlas | None = None
    atlas_registrations: dict[str, AtlasRegistration] = {}
    detail_transforms: dict[str, DetailTransform] = {}
    classifications: tuple[_ClassificationData, ...] = ()
    matches: tuple[_MatchData, ...] = ()
    if (
        manifest is not None
        and Module.DATA in manifest.included_modules
        and slices is not None
        and stainings is not None
    ):
        slices, images_by_slice = _validate_data(
            storage, slices, stainings, limits, issues
        )
    if (
        manifest is not None
        and Module.REGISTRATION in manifest.included_modules
        and slices is not None
    ):
        atlas, atlas_registrations, detail_transforms = _validate_registration(
            storage, manifest, slices, limits, issues
        )
    if (
        manifest is not None
        and Module.CLASSIFICATION in manifest.included_modules
        and slices is not None
        and stainings is not None
    ):
        classifications, matches = _validate_classification(
            storage, manifest, slices, stainings, limits, issues
        )
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
            images_by_slice,
            atlas,
            atlas_registrations,
            detail_transforms,
            classifications,
            matches,
            Module.REGISTRATION in manifest.included_modules,
            Module.CLASSIFICATION in manifest.included_modules,
        ),
        report,
    )


def validate_export(
    source: str | Path,
    *,
    limits: ExportLimits | None = None,
) -> ValidationReport:
    """Validate a local v2 ZIP archive or extracted directory.

    Parameters
    ----------
    source
        Path to a NeuroQP export ZIP archive or extracted directory.
    limits
        Optional resource limits for archive and metadata reads. Mandatory path
        and pickle protections remain enabled.

    Returns
    -------
    ValidationReport
        An aggregate report. A valid export has no issues.
    """

    export, report = _load(source, limits or ExportLimits())
    if export is not None:
        export.close()
    return report


def open_export(
    source: str | Path,
    *,
    limits: ExportLimits | None = None,
) -> ProjectExport:
    """Open and validate a local v2 ZIP archive or extracted directory.

    Parameters
    ----------
    source
        Path to a NeuroQP export ZIP archive or extracted directory.
    limits
        Optional resource limits for archive and metadata reads. Mandatory path
        and pickle protections remain enabled.

    Returns
    -------
    ProjectExport
        The open, validated project export.

    Raises
    ------
    InvalidExportError
        If the export fails validation.
    UnsupportedVersionError
        If the export format version is unsupported.

    Notes
    -----
    Use the returned object as a context manager so its storage is closed
    promptly.
    """

    export, report = _load(source, limits or ExportLimits())
    if export is not None:
        return export
    error_type = (
        UnsupportedVersionError
        if any(issue.code == "unsupported_version" for issue in report.issues)
        else InvalidExportError
    )
    raise error_type(report)
