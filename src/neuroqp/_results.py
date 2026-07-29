"""Loaded scientific result containers."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import numpy.typing as npt

from ._objects import _Display
from .models import ClassificationResultInfo, MatchResultInfo

Array = npt.NDArray[Any]


@dataclass(frozen=True, repr=False)
class ClassificationResult(_Display):
    """Store aligned classification arrays for one slice.

    Attributes
    ----------
    metadata
        Slice, staining, classifier, lineage, and timestamp metadata.
    cell_ids
        ``(N,)`` ``int32`` labels from the source detection mask.
    centroids
        ``(N, 2)`` ``float32`` pixel coordinates in ``(x, y)`` order. The
        origin is the top-left of the source detection image or mask; x
        increases right and y increases down.
    probabilities
        ``(N,)`` ``float32`` classifier probabilities.
    is_positive
        ``(N,)`` boolean mask. It is the authoritative exported classification
        and equals ``probabilities >= threshold``.
    threshold
        Probability threshold used for this slice.

    Notes
    -----
    Every row index refers to the same detected cell across all arrays.
    Coordinates are image pixels, not micrometres or atlas coordinates.
    """

    metadata: ClassificationResultInfo
    cell_ids: Array
    centroids: Array
    probabilities: Array
    is_positive: Array
    threshold: float

    @property
    def positive_centroids(self) -> Array:
        """Return ``centroids`` rows classified as positive."""

        return self.centroids[self.is_positive]

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("slice_id", self.metadata.slice_id),
            ("cells", len(self.cell_ids)),
            ("positive", int(self.is_positive.sum())),
            ("threshold", self.threshold),
        )


@dataclass(frozen=True, repr=False)
class ClassificationResults(_Display):
    """Store aligned classification arrays concatenated across slices.

    Attributes
    ----------
    cell_ids
        ``(N,)`` ``int32`` cell labels. Labels are unique only within a slice.
    slice_ids
        ``(N,)`` slice identifiers aligned with every other array.
    centroids
        ``(N, 2)`` ``float32`` source-image pixel coordinates in ``(x, y)`` order.
    probabilities
        ``(N,)`` ``float32`` classifier probabilities.
    is_positive
        ``(N,)`` authoritative boolean classification mask.
    by_slice
        Read-only mapping from slice ID to its :class:`ClassificationResult`.

    Notes
    -----
    Use ``(slice_id, cell_id)`` as a cell key. Thresholds can differ by slice
    and remain available through :attr:`by_slice`.
    """

    cell_ids: Array
    slice_ids: Array
    centroids: Array
    probabilities: Array
    is_positive: Array
    by_slice: MappingProxyType[str, ClassificationResult]

    @property
    def positive_centroids(self) -> Array:
        """Return ``centroids`` rows classified as positive."""

        return self.centroids[self.is_positive]

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("slices", len(self.by_slice)),
            ("cells", len(self.cell_ids)),
            ("positive", int(self.is_positive.sum())),
        )

    @classmethod
    def from_results(
        cls, results: tuple[ClassificationResult, ...]
    ) -> ClassificationResults:
        if not results:
            return cls(
                np.empty(0, dtype=np.int32),
                np.empty(0, dtype=str),
                np.empty((0, 2), dtype=np.float32),
                np.empty(0, dtype=np.float32),
                np.empty(0, dtype=bool),
                MappingProxyType({}),
            )
        return cls(
            np.concatenate([result.cell_ids for result in results]),
            np.concatenate(
                [
                    np.full(result.cell_ids.shape, result.metadata.slice_id)
                    for result in results
                ]
            ),
            np.concatenate([result.centroids for result in results]),
            np.concatenate([result.probabilities for result in results]),
            np.concatenate([result.is_positive for result in results]),
            MappingProxyType({result.metadata.slice_id: result for result in results}),
        )


@dataclass(frozen=True, repr=False)
class MatchResult(_Display):
    """Store aligned one-to-one cell matches for one slice.

    Attributes
    ----------
    metadata
        Slice metadata and the actual staining and detection run assigned to each side.
    cell_ids_a, cell_ids_b
        ``(M,)`` ``int32`` cell labels for sides A and B.
    centroids_a, centroids_b
        ``(M, 2)`` ``float32`` source-mask pixel coordinates in ``(x, y)``
        order for the corresponding side.
    intersection_area
        ``(M,)`` ``int32`` overlap area in pixels.
    area_a, area_b
        ``(M,)`` ``int32`` cell-mask areas in pixels for each side.
    overlap_fraction_a, overlap_fraction_b
        Intersection area divided by the corresponding side's area.
    overlap_fraction_min
        Smaller of the two side-specific overlap fractions.
    iou
        Intersection over union: ``intersection / (area_a + area_b - intersection)``.
    algorithm_version
        Matching algorithm version.
    overlap_threshold
        Minimum ``overlap_fraction_min`` retained by the matching algorithm.

    Notes
    -----
    Every row index describes one matched pair. Read side identities from
    ``metadata.side_a`` and ``metadata.side_b``; do not infer them from the
    pair key.
    """

    metadata: MatchResultInfo
    cell_ids_a: Array
    cell_ids_b: Array
    centroids_a: Array
    centroids_b: Array
    intersection_area: Array
    area_a: Array
    area_b: Array
    overlap_fraction_a: Array
    overlap_fraction_b: Array
    overlap_fraction_min: Array
    iou: Array
    algorithm_version: str
    overlap_threshold: float

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("slice_id", self.metadata.slice_id),
            ("matches", len(self.cell_ids_a)),
            ("algorithm_version", self.algorithm_version),
            ("overlap_threshold", self.overlap_threshold),
        )


@dataclass(frozen=True, repr=False)
class MatchResults(_Display):
    """Store aligned cell-match arrays concatenated across slices.

    Attributes
    ----------
    slice_ids
        ``(M,)`` slice identifiers aligned with every other array.
    cell_ids_a, cell_ids_b
        ``(M,)`` ``int32`` cell labels for sides A and B. Labels are unique
        only within a slice.
    centroids_a, centroids_b
        ``(M, 2)`` ``float32`` source-mask pixel coordinates in ``(x, y)`` order.
    intersection_area, area_a, area_b
        ``(M,)`` pixel-area arrays.
    overlap_fraction_a, overlap_fraction_b
        ``(M,)`` side-specific intersection fractions.
    overlap_fraction_min
        ``(M,)`` smaller side-specific overlap fraction.
    iou
        ``(M,)`` intersection-over-union values.
    by_slice
        Read-only mapping from slice ID to its :class:`MatchResult`.

    Notes
    -----
    Use ``(slice_id, cell_id)`` to identify cells. Side identities and
    thresholds remain available through :attr:`by_slice`.
    """

    slice_ids: Array
    cell_ids_a: Array
    cell_ids_b: Array
    centroids_a: Array
    centroids_b: Array
    intersection_area: Array
    area_a: Array
    area_b: Array
    overlap_fraction_a: Array
    overlap_fraction_b: Array
    overlap_fraction_min: Array
    iou: Array
    by_slice: MappingProxyType[str, MatchResult]

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (("slices", len(self.by_slice)), ("matches", len(self.cell_ids_a)))

    @classmethod
    def from_results(cls, results: tuple[MatchResult, ...]) -> MatchResults:
        names = (
            "cell_ids_a",
            "cell_ids_b",
            "centroids_a",
            "centroids_b",
            "intersection_area",
            "area_a",
            "area_b",
            "overlap_fraction_a",
            "overlap_fraction_b",
            "overlap_fraction_min",
            "iou",
        )
        dtypes = {
            "cell_ids_a": np.int32,
            "cell_ids_b": np.int32,
            "intersection_area": np.int32,
            "area_a": np.int32,
            "area_b": np.int32,
        }
        arrays: dict[str, Array] = {
            name: (
                np.concatenate([getattr(result, name) for result in results])
                if results
                else np.empty(
                    (0, 2) if name.startswith("centroids") else 0,
                    dtype=dtypes.get(name, np.float32),
                )
            )
            for name in names
        }
        slice_ids = (
            np.concatenate(
                [
                    np.full(result.cell_ids_a.shape, result.metadata.slice_id)
                    for result in results
                ]
            )
            if results
            else np.empty(0, dtype=str)
        )
        return cls(
            slice_ids,
            arrays["cell_ids_a"],
            arrays["cell_ids_b"],
            arrays["centroids_a"],
            arrays["centroids_b"],
            arrays["intersection_area"],
            arrays["area_a"],
            arrays["area_b"],
            arrays["overlap_fraction_a"],
            arrays["overlap_fraction_b"],
            arrays["overlap_fraction_min"],
            arrays["iou"],
            MappingProxyType({result.metadata.slice_id: result for result in results}),
        )
