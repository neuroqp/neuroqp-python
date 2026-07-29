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
    """Provide classifier metadata and results for one staining.

    Attributes
    ----------
    staining
        Classified project staining.
    classifier
        Selected classifier metadata.
    training_summary
        Training summary current at export time.
    training_samples
        Exported positive and negative training samples.
    result_index
        Slice-level result metadata available for lazy loading.
    omitted_slices
        Documented slices without a result.
    """

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
        """Filter exported training samples.

        Parameters
        ----------
        slice
            Slice object, metadata record, or ID to include.
        label
            Exported label, normally ``"on"`` or ``"off"``.
        cell_id
            Cell label to include.

        Returns
        -------
        tuple of TrainingSample
            Samples matching every supplied filter.
        """

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
        """Filter slices that have no classification result.

        Parameters
        ----------
        slice
            Slice object, metadata record, or ID to include.
        reason_code
            Stable exporter reason code to include.

        Returns
        -------
        tuple of SliceExclusion
            Omissions matching every supplied filter.
        """

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
        """Get result metadata for one slice without loading arrays.

        Parameters
        ----------
        slice_
            Slice object, metadata record, or ID.

        Returns
        -------
        ClassificationResultInfo
            Slice-level result metadata.

        Raises
        ------
        ObjectNotFoundError
            If the slice has no classification result.
        """

        slice_id = _object_id(slice_)
        return _one(
            tuple(item for item in self.result_index if item.slice_id == slice_id),
            "classification result",
            slice_id,
        )

    def load_result(self, slice_: Slice | SliceMetadata | str) -> ClassificationResult:
        """Load and validate one slice's classification arrays.

        Parameters
        ----------
        slice_
            Slice object, metadata record, or ID.

        Returns
        -------
        ClassificationResult
            Aligned cell IDs, centroids, probabilities, and classifications.

        Raises
        ------
        ObjectNotFoundError
            If the slice has no classification result.
        InvalidExportError
            If the stored arrays fail validation.
        ClosedExportError
            If the parent export is closed.
        """

        self._export._ensure_open()
        return _load_classification(self._export._storage, self.result_info(slice_))

    def load_results(self) -> ClassificationResults:
        """Load and concatenate every available slice result.

        Returns
        -------
        ClassificationResults
            Aligned arrays with a slice ID for every detected cell.

        Raises
        ------
        InvalidExportError
            If any stored result fails validation.
        ClosedExportError
            If the parent export is closed.
        """

        return ClassificationResults.from_results(
            tuple(self.load_result(item.slice_id) for item in self.result_index)
        )


class Match(_Display):
    """Provide cell-match metadata and results for one staining pair.

    Attributes
    ----------
    pair_key
        Opaque exported key used to retrieve this match.
    staining_a, staining_b
        Stainings in the exported pair definition. Read each result's metadata
        for its actual NPZ side orientation.
    result_index
        Slice-level match metadata available for lazy loading.
    omitted_slices
        Documented slices without a match result.
    """

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
        """Filter slices that have no match result.

        Parameters
        ----------
        slice
            Slice object, metadata record, or ID to include.
        reason_code
            Stable exporter reason code to include.

        Returns
        -------
        tuple of SliceExclusion
            Omissions matching every supplied filter.
        """

        slice_id = _object_id(slice) if slice is not None else None
        return tuple(
            item
            for item in self.omitted_slices
            if (slice_id is None or item.slice_id == slice_id)
            and (reason_code is None or item.reason_code == reason_code)
        )

    def result_info(self, slice_: Slice | SliceMetadata | str) -> MatchResultInfo:
        """Get match metadata for one slice without loading arrays.

        Parameters
        ----------
        slice_
            Slice object, metadata record, or ID.

        Returns
        -------
        MatchResultInfo
            Slice-level match metadata, including side identities.

        Raises
        ------
        ObjectNotFoundError
            If the slice has no match result.
        """

        slice_id = _object_id(slice_)
        return _one(
            tuple(item for item in self.result_index if item.slice_id == slice_id),
            "match result",
            slice_id,
        )

    def load_result(self, slice_: Slice | SliceMetadata | str) -> MatchResult:
        """Load and validate one slice's match arrays.

        Parameters
        ----------
        slice_
            Slice object, metadata record, or ID.

        Returns
        -------
        MatchResult
            Aligned one-to-one cell-pair arrays.

        Raises
        ------
        ObjectNotFoundError
            If the slice has no match result.
        InvalidExportError
            If the stored arrays fail validation.
        ClosedExportError
            If the parent export is closed.
        """

        self._export._ensure_open()
        return _load_match(self._export._storage, self.result_info(slice_))

    def load_results(self) -> MatchResults:
        """Load and concatenate every available slice match.

        Returns
        -------
        MatchResults
            Aligned arrays with a slice ID for every matched pair.

        Raises
        ------
        InvalidExportError
            If any stored match fails validation.
        ClosedExportError
            If the parent export is closed.
        """

        return MatchResults.from_results(
            tuple(self.load_result(item.slice_id) for item in self.result_index)
        )


class ClassificationModule(_Display):
    """Provide the classifications and cell matches included in an export.

    Attributes
    ----------
    classifications
        Selected classifications, one per included staining.
    matches
        Included staining-pair cell matches.
    """

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
        """Get the selected classification for a staining.

        Parameters
        ----------
        staining
            Staining object, metadata record, exact name, or ID.

        Returns
        -------
        Classification
            Selected classifier and available results.

        Raises
        ------
        ObjectNotFoundError
            If the export has no classification for the staining.
        AmbiguousNameError
            If the staining name is not unique.
        """

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
        """Get a staining-pair match by its exported key.

        Parameters
        ----------
        pair_key
            Key discovered from :attr:`matches`.

        Returns
        -------
        Match
            Match metadata and available slice results.

        Raises
        ------
        ObjectNotFoundError
            If the pair key is not present.
        """

        return _one(
            tuple(item for item in self.matches if item.pair_key == pair_key),
            "match",
            pair_key,
        )
