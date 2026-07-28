"""v2 reader and aggregate metadata validator."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from ._api import ProjectExport as ProjectExport
from ._api import _ClassificationData, _MatchData
from ._storage import Storage, StorageError, open_storage
from .errors import InvalidExportError, UnsupportedVersionError
from .models import (
    Animal,
    Atlas,
    AtlasRegistration,
    BrainRegion,
    ClassificationResultInfo,
    ClassifierMetadata,
    DetailTransform,
    EntityReference,
    ExportLimits,
    ExportMetadata,
    Image,
    Manifest,
    MatchResultInfo,
    Module,
    Point,
    ProjectMetadata,
    RegistrationLandmark,
    Slice,
    SliceExclusion,
    Staining,
    TrainingSample,
    TrainingSummary,
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


def _exclusions(
    value: Any,
    path: str,
    field: str,
    issues: list[ValidationIssue],
) -> tuple[SliceExclusion, ...]:
    result = _parse_list(SliceExclusion, value, path, issues)
    if result is None:
        issues.append(_issue(path, "invalid_field", f"{field} must be an array", field))
        return ()
    return result


def _reference_id(
    value: Any,
    path: str,
    field: str,
    issues: list[ValidationIssue],
) -> str | None:
    reference = _parse_model(EntityReference, value, path, issues, prefix=f"{field}.")
    return reference.id if reference is not None else None


def _validate_classification(
    storage: Storage,
    manifest: Manifest,
    slices: tuple[Slice, ...],
    stainings: tuple[Staining, ...],
    limits: ExportLimits,
    issues: list[ValidationIssue],
) -> tuple[tuple[_ClassificationData, ...], tuple[_MatchData, ...]]:
    path = "classification/manifest.json"
    value = _read_json(storage, path, limits, issues)
    if not isinstance(value, dict):
        return (), ()
    if value.get("exportVersion") != "v2":
        issues.append(_issue(path, "unsupported_version", "exportVersion must be v2"))
    staining_entries = value.get("stainings")
    match_entries = value.get("matches")
    if not isinstance(staining_entries, list):
        issues.append(
            _issue(path, "invalid_field", "stainings must be an array", "stainings")
        )
        staining_entries = []
    if not isinstance(match_entries, list):
        issues.append(
            _issue(path, "invalid_field", "matches must be an array", "matches")
        )
        match_entries = []
    staining_ids = {item.id for item in stainings}
    slice_ids = {item.id for item in slices}
    classifications: list[_ClassificationData] = []
    for index, entry in enumerate(staining_entries):
        prefix = f"stainings.{index}"
        if not isinstance(entry, dict):
            issues.append(
                _issue(path, "invalid_field", "entry must be an object", prefix)
            )
            continue
        staining_id = _reference_id(
            entry.get("staining"), path, f"{prefix}.staining", issues
        )
        manifest_classifier_id = _reference_id(
            entry.get("classifier"), path, f"{prefix}.classifier", issues
        )
        paths: dict[str, str] = {}
        for field in (
            "classifierPath",
            "trainingSummaryPath",
            "trainingSamplesPath",
            "resultIndexPath",
        ):
            member = entry.get(field)
            if not isinstance(member, str) or member not in storage.members:
                issues.append(
                    _issue(
                        path,
                        "invalid_reference",
                        f"{field} must name an existing member",
                        f"{prefix}.{field}",
                    )
                )
            else:
                paths[field] = member
        omitted = _exclusions(
            entry.get("exclusions"), path, f"{prefix}.exclusions", issues
        )
        if staining_id is None or manifest_classifier_id is None or len(paths) != 4:
            continue
        if staining_id not in staining_ids:
            issues.append(
                _issue(path, "unknown_staining", f"unknown staining {staining_id}")
            )
        classifier = _parse_model(
            ClassifierMetadata,
            _read_json(storage, paths["classifierPath"], limits, issues),
            paths["classifierPath"],
            issues,
        )
        training = _parse_model(
            TrainingSummary,
            _read_json(storage, paths["trainingSummaryPath"], limits, issues),
            paths["trainingSummaryPath"],
            issues,
        )
        samples = _read_jsonl(
            TrainingSample,
            storage,
            paths["trainingSamplesPath"],
            limits,
            issues,
        )
        index_value = _read_json(storage, paths["resultIndexPath"], limits, issues)
        result_index: tuple[ClassificationResultInfo, ...] | None = None
        index_staining_id: str | None = None
        index_classifier_id: str | None = None
        if isinstance(index_value, dict):
            index_staining_id = _reference_id(
                index_value.get("staining"),
                paths["resultIndexPath"],
                "staining",
                issues,
            )
            index_classifier_id = _reference_id(
                index_value.get("classifier"),
                paths["resultIndexPath"],
                "classifier",
                issues,
            )
            result_index = _parse_list(
                ClassificationResultInfo,
                index_value.get("slices"),
                paths["resultIndexPath"],
                issues,
            )
        if classifier is not None:
            selected = manifest.selected_classifier_head_ids_by_staining.get(
                staining_id
            )
            if (
                classifier.staining.id != staining_id
                or index_staining_id != staining_id
                or index_classifier_id != classifier.id
                or manifest_classifier_id != classifier.id
                or (selected is not None and selected != classifier.id)
            ):
                issues.append(
                    _issue(
                        paths["classifierPath"],
                        "inconsistent_reference",
                        "staining or classifier identity is inconsistent",
                    )
                )
            linked_run = manifest.linked_training_run_ids_by_staining.get(staining_id)
            if linked_run != classifier.training_run_id:
                issues.append(
                    _issue(
                        paths["classifierPath"],
                        "inconsistent_reference",
                        "trainingRunId does not agree with manifest.json",
                        "trainingRunId",
                    )
                )
        if training is not None and training.staining.id != staining_id:
            issues.append(
                _issue(
                    paths["trainingSummaryPath"],
                    "inconsistent_reference",
                    "staining identity does not agree with classification manifest",
                )
            )
        for sample in samples or ():
            if sample.staining_id != staining_id or sample.slice_id not in slice_ids:
                issues.append(
                    _issue(
                        paths["trainingSamplesPath"],
                        "invalid_reference",
                        "training sample references an unknown slice or staining",
                    )
                )
        for exclusion in omitted:
            if exclusion.slice_id not in slice_ids:
                issues.append(
                    _issue(
                        path,
                        "invalid_reference",
                        "exclusion references an unknown slice",
                        f"{prefix}.exclusions",
                    )
                )
        result_slice_ids: list[str] = []
        for result in result_index or ():
            result_slice_ids.append(result.slice_id)
            if (
                result.slice_id not in slice_ids
                or result.staining_id != staining_id
                or classifier is None
                or result.classifier_id != classifier.id
            ):
                issues.append(
                    _issue(
                        paths["resultIndexPath"],
                        "invalid_reference",
                        "result references an unknown or inconsistent object",
                    )
                )
            if result.npz_path not in storage.members:
                issues.append(
                    _issue(
                        paths["resultIndexPath"],
                        "invalid_reference",
                        "npzPath must name an existing member",
                        "npzPath",
                    )
                )
        _check_duplicates(
            paths["resultIndexPath"],
            "slice result",
            result_slice_ids,
            issues,
            code="duplicate_result",
        )
        if (
            classifier is not None
            and training is not None
            and samples is not None
            and result_index is not None
        ):
            classifications.append(
                _ClassificationData(
                    staining_id,
                    classifier,
                    training,
                    samples,
                    result_index,
                    omitted,
                )
            )
    matches: list[_MatchData] = []
    for index, entry in enumerate(match_entries):
        prefix = f"matches.{index}"
        if not isinstance(entry, dict):
            issues.append(
                _issue(path, "invalid_field", "entry must be an object", prefix)
            )
            continue
        match_path = entry.get("matchPath")
        if not isinstance(match_path, str) or match_path not in storage.members:
            issues.append(
                _issue(
                    path,
                    "invalid_reference",
                    "matchPath must name an existing member",
                    f"{prefix}.matchPath",
                )
            )
            continue
        match_value = _read_json(storage, match_path, limits, issues)
        if not isinstance(match_value, dict):
            continue
        pair_key = match_value.get("pairKey")
        manifest_staining_a = _reference_id(
            entry.get("stainingA"), path, f"{prefix}.stainingA", issues
        )
        manifest_staining_b = _reference_id(
            entry.get("stainingB"), path, f"{prefix}.stainingB", issues
        )
        staining_a = _reference_id(
            match_value.get("stainingA"), match_path, "stainingA", issues
        )
        staining_b = _reference_id(
            match_value.get("stainingB"), match_path, "stainingB", issues
        )
        omitted = _exclusions(
            match_value.get("exclusions"), match_path, "exclusions", issues
        )
        match_result_index = _parse_list(
            MatchResultInfo, match_value.get("slices"), match_path, issues
        )
        if (
            not isinstance(pair_key, str)
            or staining_a is None
            or staining_b is None
            or match_result_index is None
        ):
            issues.append(
                _issue(match_path, "invalid_field", "match identity is invalid")
            )
            continue
        if entry.get("pairKey") != pair_key:
            issues.append(
                _issue(
                    match_path,
                    "inconsistent_reference",
                    "pairKey does not agree with classification manifest",
                )
            )
        if (manifest_staining_a, manifest_staining_b) != (staining_a, staining_b):
            issues.append(
                _issue(
                    match_path,
                    "inconsistent_reference",
                    "staining identities do not agree with classification manifest",
                )
            )
        if staining_a not in staining_ids or staining_b not in staining_ids:
            issues.append(
                _issue(
                    match_path,
                    "unknown_staining",
                    "match references an unknown staining",
                )
            )
        for exclusion in omitted:
            if exclusion.slice_id not in slice_ids:
                issues.append(
                    _issue(
                        match_path,
                        "invalid_reference",
                        "exclusion references an unknown slice",
                        "exclusions",
                    )
                )
        result_slice_ids = []
        for match_result in match_result_index:
            result_slice_ids.append(match_result.slice_id)
            if (
                match_result.slice_id not in slice_ids
                or {
                    match_result.side_a.staining.id,
                    match_result.side_b.staining.id,
                }
                != {staining_a, staining_b}
                or match_result.npz_path not in storage.members
            ):
                issues.append(
                    _issue(
                        match_path,
                        "invalid_reference",
                        "match result references an unknown or inconsistent object",
                    )
                )
        _check_duplicates(
            match_path,
            "slice result",
            result_slice_ids,
            issues,
            code="duplicate_result",
        )
        matches.append(
            _MatchData(
                pair_key,
                staining_a,
                staining_b,
                match_result_index,
                omitted,
            )
        )
    _check_duplicates(
        path,
        "classification staining",
        [item.staining_id for item in classifications],
        issues,
        code="duplicate_result",
    )
    _check_duplicates(
        path,
        "pairKey",
        [item.pair_key for item in matches],
        issues,
        code="duplicate_result",
    )
    return tuple(classifications), tuple(matches)


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
