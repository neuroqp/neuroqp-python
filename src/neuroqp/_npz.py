"""Safe NumPy result loading and invariant validation."""

from __future__ import annotations

from io import BytesIO
from typing import Any, cast

import numpy as np

from ._objects import _invalid
from ._results import Array, ClassificationResult, MatchResult
from ._storage import Storage, StorageError
from .models import ClassificationResultInfo, MatchResultInfo


def _read_npz(storage: Storage, path: str) -> Any:
    try:
        return np.load(BytesIO(storage.read(path)), allow_pickle=False)
    except (FileNotFoundError, StorageError, OSError, ValueError) as error:
        _invalid(path, "invalid_npz", str(error))


def _array(
    archive: Any,
    path: str,
    name: str,
    dtype: np.dtype[Any],
    *,
    length: int | None = None,
) -> Array:
    try:
        value = archive[name]
    except (KeyError, ValueError) as error:
        _invalid(path, "invalid_array", str(error), name)
    if value.dtype != dtype or value.ndim != 1:
        _invalid(
            path,
            "invalid_array",
            f"expected one-dimensional {dtype.name} array",
            name,
        )
    if length is not None and len(value) != length:
        _invalid(path, "array_length", f"expected {length} values", name)
    return cast(Array, value.copy())


def _load_classification(
    storage: Storage, info: ClassificationResultInfo
) -> ClassificationResult:
    archive = _read_npz(storage, info.npz_path)
    try:
        cell_ids = _array(archive, info.npz_path, "cell_ids", np.dtype("int32"))
        length = len(cell_ids)
        x = _array(
            archive,
            info.npz_path,
            "centroids_x",
            np.dtype("float32"),
            length=length,
        )
        y = _array(
            archive,
            info.npz_path,
            "centroids_y",
            np.dtype("float32"),
            length=length,
        )
        probabilities = _array(
            archive,
            info.npz_path,
            "intensities",
            np.dtype("float32"),
            length=length,
        )
        raw_positive = _array(
            archive,
            info.npz_path,
            "is_on",
            np.dtype("uint8"),
            length=length,
        )
        threshold_array = _array(
            archive, info.npz_path, "threshold", np.dtype("float32"), length=1
        )
    finally:
        archive.close()
    if not np.all((raw_positive == 0) | (raw_positive == 1)):
        _invalid(
            info.npz_path,
            "invalid_array",
            "is_on values must be 0 or 1",
            "is_on",
        )
    threshold = float(threshold_array[0])
    is_positive = raw_positive.astype(bool)
    if not np.array_equal(is_positive, probabilities >= threshold):
        _invalid(
            info.npz_path,
            "threshold_mismatch",
            "is_on does not agree with intensities >= threshold",
            "is_on",
        )
    if info.threshold is not None and not np.isclose(info.threshold, threshold):
        _invalid(
            info.npz_path,
            "threshold_mismatch",
            "array threshold does not agree with result index",
            "threshold",
        )
    if info.on_count is not None and info.on_count != int(is_positive.sum()):
        _invalid(
            info.npz_path,
            "count_mismatch",
            "onCount does not agree with is_on",
            "is_on",
        )
    if info.off_count is not None and info.off_count != length - int(is_positive.sum()):
        _invalid(
            info.npz_path,
            "count_mismatch",
            "offCount does not agree with is_on",
            "is_on",
        )
    return ClassificationResult(
        info,
        cell_ids,
        np.column_stack((x, y)),
        probabilities,
        is_positive,
        threshold,
    )


def _load_match(storage: Storage, info: MatchResultInfo) -> MatchResult:
    archive = _read_npz(storage, info.npz_path)
    try:
        cell_ids_a = _array(archive, info.npz_path, "cell_ids_a", np.dtype("int32"))
        length = len(cell_ids_a)
        values = {
            name: _array(archive, info.npz_path, name, dtype, length=length)
            for name, dtype in (
                ("cell_ids_b", np.dtype("int32")),
                ("intersection_area", np.dtype("int32")),
                ("area_a", np.dtype("int32")),
                ("area_b", np.dtype("int32")),
                ("overlap_fraction_a", np.dtype("float32")),
                ("overlap_fraction_b", np.dtype("float32")),
                ("overlap_fraction_min", np.dtype("float32")),
                ("iou", np.dtype("float32")),
            )
        }
        centroids = (
            {
                side: np.column_stack(
                    (
                        _array(
                            archive,
                            info.npz_path,
                            f"centroids_x_{side}",
                            np.dtype("float32"),
                            length=length,
                        ),
                        _array(
                            archive,
                            info.npz_path,
                            f"centroids_y_{side}",
                            np.dtype("float32"),
                            length=length,
                        ),
                    )
                )
                for side in ("a", "b")
            }
            if length
            else {
                "a": np.empty((0, 2), dtype=np.float32),
                "b": np.empty((0, 2), dtype=np.float32),
            }
        )
        try:
            schema_version = archive["schema_version"]
            algorithm_version = archive["algorithm_version"]
            overlap_threshold = archive["overlap_threshold"]
        except (KeyError, ValueError) as error:
            _invalid(info.npz_path, "invalid_array", str(error))
    finally:
        archive.close()
    if (
        schema_version.shape != ()
        or schema_version.dtype != np.dtype("int32")
        or int(schema_version) != 1
    ):
        _invalid(
            info.npz_path,
            "invalid_array",
            "schema_version must be scalar int32 value 1",
            "schema_version",
        )
    if algorithm_version.shape != () or algorithm_version.dtype.kind != "U":
        _invalid(
            info.npz_path,
            "invalid_array",
            "algorithm_version must be a Unicode scalar",
            "algorithm_version",
        )
    if overlap_threshold.shape != () or overlap_threshold.dtype != np.dtype("float32"):
        _invalid(
            info.npz_path,
            "invalid_array",
            "overlap_threshold must be a float32 scalar",
            "overlap_threshold",
        )
    algorithm = str(algorithm_version)
    threshold = float(overlap_threshold)
    fractions = (
        values["overlap_fraction_a"],
        values["overlap_fraction_b"],
        values["overlap_fraction_min"],
        values["iou"],
    )
    if any(np.any((value < 0) | (value > 1)) for value in fractions):
        _invalid(
            info.npz_path,
            "invalid_fraction",
            "overlap fractions and IoU must be between 0 and 1",
        )
    if np.any(values["overlap_fraction_min"] < threshold):
        _invalid(
            info.npz_path,
            "threshold_mismatch",
            "overlap_fraction_min is below overlap_threshold",
            "overlap_fraction_min",
        )
    if (
        len(np.unique(cell_ids_a)) != length
        or len(np.unique(values["cell_ids_b"])) != length
    ):
        _invalid(
            info.npz_path,
            "duplicate_cell_id",
            "cell IDs must be unique on each match side",
        )
    if algorithm != info.algorithm_version or not np.isclose(
        threshold, info.overlap_threshold
    ):
        _invalid(
            info.npz_path,
            "index_mismatch",
            "algorithm metadata does not agree with match index",
        )
    if info.matched_count is not None and info.matched_count != length:
        _invalid(
            info.npz_path,
            "count_mismatch",
            "matchedCount does not agree with result arrays",
        )
    return MatchResult(
        info,
        cell_ids_a,
        values["cell_ids_b"],
        centroids["a"],
        centroids["b"],
        values["intersection_area"],
        values["area_a"],
        values["area_b"],
        values["overlap_fraction_a"],
        values["overlap_fraction_b"],
        values["overlap_fraction_min"],
        values["iou"],
        algorithm,
        threshold,
    )
