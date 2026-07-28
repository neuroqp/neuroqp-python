"""v2 classification metadata adapter and validator."""

from __future__ import annotations

from typing import Any

from ._classification import _ClassificationData, _MatchData
from ._storage import Storage
from ._validation import (
    _check_duplicates,
    _issue,
    _parse_list,
    _parse_model,
    _read_json,
    _read_jsonl,
)
from .models import (
    ClassificationResultInfo,
    ClassifierMetadata,
    EntityReference,
    ExportLimits,
    Manifest,
    MatchResultInfo,
    Slice,
    SliceExclusion,
    Staining,
    TrainingSample,
    TrainingSummary,
    ValidationIssue,
)


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
