"""Classification and cell-match navigation API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._npz import _load_classification, _load_match
from ._objects import Slice, Staining, _Display, _object_id, _one
from ._results import (
    ClassificationResult,
    ClassificationResults,
    MatchResult,
    MatchResults,
)
from .models import (
    ClassificationResultInfo,
    ClassifierMetadata,
    MatchResultInfo,
    SliceExclusion,
    TrainingSample,
    TrainingSummary,
)
from .models import Slice as SliceMetadata
from .models import Staining as StainingMetadata

if TYPE_CHECKING:
    from ._project import ProjectExport


@dataclass(frozen=True)
class _ClassificationData:
    staining_id: str
    classifier: ClassifierMetadata
    training_summary: TrainingSummary
    training_samples: tuple[TrainingSample, ...]
    result_index: tuple[ClassificationResultInfo, ...]
    omitted_slices: tuple[SliceExclusion, ...]


@dataclass(frozen=True)
class _MatchData:
    pair_key: str
    staining_a_id: str
    staining_b_id: str
    result_index: tuple[MatchResultInfo, ...]
    omitted_slices: tuple[SliceExclusion, ...]


class Classification(_Display):
    """One selected staining's classifier and results."""

    def __init__(self, export: ProjectExport, data: _ClassificationData) -> None:
        self._export = export
        self._data = data
        self.staining = export.staining(data.staining_id)
        self.classifier = data.classifier
        self.training_summary = data.training_summary
        self.training_samples = data.training_samples
        self.result_index = data.result_index
        self.omitted_slices = data.omitted_slices

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("staining", self.staining.metadata.name),
            ("classifier", self.classifier.display_name),
            ("results", len(self.result_index)),
            ("training_samples", len(self.training_samples)),
            ("omitted_slices", len(self.omitted_slices)),
        )

    def find_training_samples(
        self,
        *,
        slice: Slice | SliceMetadata | str | None = None,
        label: str | None = None,
        cell_id: int | None = None,
    ) -> tuple[TrainingSample, ...]:
        """Filter eager training samples."""

        slice_id = _object_id(slice) if slice is not None else None
        return tuple(
            sample
            for sample in self.training_samples
            if (slice_id is None or sample.slice_id == slice_id)
            and (label is None or sample.label == label)
            and (cell_id is None or sample.cell_id == cell_id)
        )

    def find_omitted_slices(
        self,
        *,
        slice: Slice | SliceMetadata | str | None = None,
        reason_code: str | None = None,
    ) -> tuple[SliceExclusion, ...]:
        """Filter documented result omissions."""

        slice_id = _object_id(slice) if slice is not None else None
        return tuple(
            item
            for item in self.omitted_slices
            if (slice_id is None or item.slice_id == slice_id)
            and (reason_code is None or item.reason_code == reason_code)
        )

    def result_info(
        self, slice_: Slice | SliceMetadata | str
    ) -> ClassificationResultInfo:
        """Get result index metadata for one slice."""

        slice_id = _object_id(slice_)
        return _one(
            tuple(item for item in self.result_index if item.slice_id == slice_id),
            "classification result",
            slice_id,
        )

    def load_result(self, slice_: Slice | SliceMetadata | str) -> ClassificationResult:
        """Load and validate one slice's classification arrays."""

        self._export._ensure_open()
        return _load_classification(self._export._storage, self.result_info(slice_))

    def load_results(self) -> ClassificationResults:
        """Load and concatenate all classification results."""

        return ClassificationResults.from_results(
            tuple(self.load_result(item.slice_id) for item in self.result_index)
        )


class Match(_Display):
    """One staining-pair match and its results."""

    def __init__(self, export: ProjectExport, data: _MatchData) -> None:
        self._export = export
        self.pair_key = data.pair_key
        self.staining_a = export.staining(data.staining_a_id)
        self.staining_b = export.staining(data.staining_b_id)
        self.result_index = data.result_index
        self.omitted_slices = data.omitted_slices

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("pair_key", self.pair_key),
            ("staining_a", self.staining_a.metadata.name),
            ("staining_b", self.staining_b.metadata.name),
            ("results", len(self.result_index)),
            ("omitted_slices", len(self.omitted_slices)),
        )

    def find_omitted_slices(
        self,
        *,
        slice: Slice | SliceMetadata | str | None = None,
        reason_code: str | None = None,
    ) -> tuple[SliceExclusion, ...]:
        """Filter documented result omissions."""

        slice_id = _object_id(slice) if slice is not None else None
        return tuple(
            item
            for item in self.omitted_slices
            if (slice_id is None or item.slice_id == slice_id)
            and (reason_code is None or item.reason_code == reason_code)
        )

    def result_info(self, slice_: Slice | SliceMetadata | str) -> MatchResultInfo:
        """Get match index metadata for one slice."""

        slice_id = _object_id(slice_)
        return _one(
            tuple(item for item in self.result_index if item.slice_id == slice_id),
            "match result",
            slice_id,
        )

    def load_result(self, slice_: Slice | SliceMetadata | str) -> MatchResult:
        """Load and validate one slice's match arrays."""

        self._export._ensure_open()
        return _load_match(self._export._storage, self.result_info(slice_))

    def load_results(self) -> MatchResults:
        """Load and concatenate all match results."""

        return MatchResults.from_results(
            tuple(self.load_result(item.slice_id) for item in self.result_index)
        )


class ClassificationModule(_Display):
    """Classification and cell-match module access."""

    def __init__(
        self,
        export: ProjectExport,
        classifications: tuple[_ClassificationData, ...],
        matches: tuple[_MatchData, ...],
    ) -> None:
        self._export = export
        self.classifications = tuple(
            Classification(export, item) for item in classifications
        )
        self.matches = tuple(Match(export, item) for item in matches)

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("classifications", len(self.classifications)),
            ("matches", len(self.matches)),
        )

    def for_staining(
        self, staining: Staining | StainingMetadata | str
    ) -> Classification:
        """Get the selected classification for a staining."""

        staining_id = (
            self._export.staining_by_name(staining).id
            if isinstance(staining, str)
            and staining not in {item.id for item in self._export.stainings}
            else _object_id(staining)
        )
        return _one(
            tuple(
                item for item in self.classifications if item.staining.id == staining_id
            ),
            "classification",
            staining_id,
        )

    def match(self, pair_key: str) -> Match:
        """Get one uniquely identified staining-pair match."""

        return _one(
            tuple(item for item in self.matches if item.pair_key == pair_key),
            "match",
            pair_key,
        )
