"""Reader-bound public API and safe binary result loaders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from io import BytesIO
from types import MappingProxyType
from typing import Any, BinaryIO, Generic, NoReturn, TypeVar, cast

import numpy as np
import numpy.typing as npt

from ._storage import Storage, StorageError
from .errors import (
    AmbiguousNameError,
    ClosedExportError,
    InvalidExportError,
    ObjectNotFoundError,
)
from .models import (
    Animal as AnimalMetadata,
)
from .models import (
    Atlas,
    AtlasRegistration,
    BrainRegion,
    ClassificationResultInfo,
    ClassifierMetadata,
    DetailTransform,
    ExportMetadata,
    Manifest,
    MatchResultInfo,
    ProjectMetadata,
    SliceExclusion,
    TrainingSample,
    TrainingSummary,
    ValidationIssue,
    ValidationReport,
)
from .models import (
    Image as ImageMetadata,
)
from .models import (
    Slice as SliceMetadata,
)
from .models import (
    Staining as StainingMetadata,
)

Array = npt.NDArray[Any]
MetadataT = TypeVar("MetadataT")
ItemT = TypeVar("ItemT")


def _object_id(value: object) -> str:
    if isinstance(value, str):
        return value
    object_id = getattr(value, "id", None)
    if isinstance(object_id, str):
        return object_id
    raise TypeError("expected an object or ID string")


def _one(items: tuple[ItemT, ...], label: str, value: object) -> ItemT:
    if not items:
        raise ObjectNotFoundError(f"{label} not found: {value}")
    if len(items) > 1:
        raise AmbiguousNameError(f"{label} is ambiguous: {value}")
    return items[0]


def _invalid(path: str, code: str, message: str, field: str | None = None) -> NoReturn:
    raise InvalidExportError(
        ValidationReport(
            issues=(
                ValidationIssue(path=path, field=field, code=code, message=message),
            )
        )
    )


class _Display:
    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return ()

    def __repr__(self) -> str:
        fields = ", ".join(f"{name}={value!r}" for name, value in self._display_items())
        return f"{type(self).__name__}({fields})"

    def __str__(self) -> str:
        return repr(self)

    def _repr_html_(self) -> str:
        rows = "".join(
            f"<tr><th>{escape(name)}</th><td><code>{escape(repr(value))}</code></td></tr>"
            for name, value in self._display_items()
        )
        return (
            f'<div class="neuroqp-repr"><strong>{escape(type(self).__name__)}</strong>'
            f"<table>{rows}</table></div>"
        )


class FileArtifact(_Display):
    """A file contained in an open export."""

    def __init__(self, export: ProjectExport, path: str) -> None:
        self._export = export
        self.path = path

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (("path", self.path),)

    def open(self) -> BinaryIO:
        """Open an independent in-memory binary stream."""

        self._export._ensure_open()
        try:
            return BytesIO(self._export._storage.read(self.path))
        except (FileNotFoundError, StorageError) as error:
            _invalid(self.path, "unreadable_member", str(error))


class _Bound(_Display, Generic[MetadataT]):
    def __init__(self, export: ProjectExport, metadata: MetadataT) -> None:
        self._export = export
        self.metadata = metadata

    def __getattr__(self, name: str) -> Any:
        self._export._ensure_open()
        return getattr(self.metadata, name)


class Staining(_Bound[StainingMetadata]):
    """A project staining."""

    @property
    def id(self) -> str:
        self._export._ensure_open()
        return self.metadata.id

    @property
    def name(self) -> str:
        self._export._ensure_open()
        return self.metadata.name

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (("id", self.metadata.id), ("name", self.metadata.name))


class Animal(_Bound[AnimalMetadata]):
    """An animal and its slices."""

    @property
    def id(self) -> str:
        self._export._ensure_open()
        return self.metadata.id

    @property
    def name(self) -> str:
        self._export._ensure_open()
        return self.metadata.name

    @property
    def slices(self) -> tuple[Slice, ...]:
        return tuple(item for item in self._export.slices if item.animal.id == self.id)

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        slice_count = sum(
            item.metadata.animal_id == self.metadata.id for item in self._export._slices
        )
        return (
            ("id", self.metadata.id),
            ("name", self.metadata.name),
            ("slices", slice_count),
        )


class Image(_Bound[ImageMetadata]):
    """An exported image artifact."""

    @property
    def id(self) -> str:
        self._export._ensure_open()
        return self.metadata.id

    @property
    def slice(self) -> Slice:
        return self._export.slice(self.metadata.slice_id)

    @property
    def staining(self) -> Staining:
        return self._export.staining(self.metadata.staining_id)

    def open(self) -> BinaryIO:
        """Open the exact archived image member."""

        return FileArtifact(self._export, self.metadata.archive_path).open()

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("id", self.metadata.id),
            ("filename", self.metadata.original_filename),
            ("staining_id", self.metadata.staining_id),
            ("shape", (self.metadata.height, self.metadata.width)),
        )


class Slice(_Bound[SliceMetadata]):
    """A project slice with navigation to related objects."""

    @property
    def id(self) -> str:
        self._export._ensure_open()
        return self.metadata.id

    @property
    def name(self) -> str | None:
        self._export._ensure_open()
        return self.metadata.name

    @property
    def animal(self) -> Animal:
        return self._export.animal(self.metadata.animal_id)

    @property
    def images(self) -> tuple[Image, ...]:
        self._export._ensure_open()
        return self._export._images_by_slice.get(self.id, ())

    def image(self, image_id: str) -> Image:
        """Get this slice's uniquely identified image."""

        return _one(
            tuple(image for image in self.images if image.id == image_id),
            "image",
            image_id,
        )

    def find_images(
        self,
        *,
        staining: Staining | StainingMetadata | str | None = None,
        magnification: str | None = None,
        filename: str | None = None,
    ) -> tuple[Image, ...]:
        """Find images using any combination of common metadata fields."""

        staining_id = None
        if staining is not None:
            staining_id = (
                self._export.staining_by_name(staining).id
                if isinstance(staining, str)
                and staining not in {item.id for item in self._export.stainings}
                else _object_id(staining)
            )
        return tuple(
            image
            for image in self.images
            if (staining_id is None or image.metadata.staining_id == staining_id)
            and (magnification is None or image.metadata.magnification == magnification)
            and (filename is None or image.metadata.original_filename == filename)
        )

    @property
    def cell_mask(self) -> FileArtifact | None:
        path = f"data/slices/{self.id}/detection/cell-mask.tif"
        if path in self._export.members:
            return FileArtifact(self._export, path)
        return None

    @property
    def registration(self) -> SliceRegistration | None:
        module = self._export.registration
        return module.for_slice(self) if module is not None else None

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("id", self.metadata.id),
            ("name", self.metadata.name),
            ("animal_id", self.metadata.animal_id),
            ("slice_coordinate_mm", self.metadata.slice_coordinate_mm),
            ("images", len(self._export._images_by_slice.get(self.metadata.id, ()))),
        )


@dataclass(frozen=True, repr=False)
class SliceRegistration(_Display):
    """Available registration data for one slice."""

    slice: Slice
    atlas: Atlas
    atlas_registration: AtlasRegistration | None
    detail_transform: DetailTransform | None

    @property
    def slice_coordinate_mm(self) -> float:
        if self.atlas_registration is not None:
            return self.atlas_registration.slice_coordinate_mm
        return self.slice.metadata.slice_coordinate_mm

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("slice_id", self.slice.metadata.id),
            ("slice_coordinate_mm", self.slice_coordinate_mm),
            (
                "landmarks",
                len(self.atlas_registration.landmarks)
                if self.atlas_registration is not None
                else 0,
            ),
            ("detail_transform", self.detail_transform is not None),
        )


class Registration(_Display):
    """Registration module access."""

    def __init__(
        self,
        export: ProjectExport,
        atlas: Atlas,
        atlas_registrations: dict[str, AtlasRegistration],
        detail_transforms: dict[str, DetailTransform],
    ) -> None:
        self._export = export
        self.atlas = atlas
        self._atlas_registrations = atlas_registrations
        self._detail_transforms = detail_transforms

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("atlas", self.atlas.name),
            ("registered_slices", len(self._atlas_registrations)),
            ("detail_transforms", len(self._detail_transforms)),
        )

    def for_slice(
        self, slice_: Slice | SliceMetadata | str
    ) -> SliceRegistration | None:
        """Return available registration data for one slice."""

        slice_object = self._export.slice(_object_id(slice_))
        atlas_registration = self._atlas_registrations.get(slice_object.id)
        detail_transform = self._detail_transforms.get(slice_object.id)
        if atlas_registration is None and detail_transform is None:
            return None
        return SliceRegistration(
            slice_object, self.atlas, atlas_registration, detail_transform
        )


@dataclass(frozen=True, repr=False)
class ClassificationResult(_Display):
    """Loaded classification arrays for one slice."""

    metadata: ClassificationResultInfo
    cell_ids: Array
    centroids: Array
    probabilities: Array
    is_positive: Array
    threshold: float

    @property
    def positive_centroids(self) -> Array:
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
    """Concatenated classification arrays across slices."""

    cell_ids: Array
    slice_ids: Array
    centroids: Array
    probabilities: Array
    is_positive: Array
    by_slice: MappingProxyType[str, ClassificationResult]

    @property
    def positive_centroids(self) -> Array:
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
    """Loaded cell-match arrays for one slice."""

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
    """Concatenated match arrays across slices."""

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


class ProjectExport(_Display):
    """An open, validated NeuroQP project export."""

    def __init__(
        self,
        storage: Storage,
        manifest: Manifest,
        metadata: ExportMetadata,
        project: ProjectMetadata,
        stainings: tuple[StainingMetadata, ...],
        animals: tuple[AnimalMetadata, ...],
        slices: tuple[SliceMetadata, ...],
        brain_regions: tuple[BrainRegion, ...],
        images_by_slice: dict[str, tuple[ImageMetadata, ...]],
        atlas: Atlas | None,
        atlas_registrations: dict[str, AtlasRegistration],
        detail_transforms: dict[str, DetailTransform],
        classifications: tuple[_ClassificationData, ...],
        matches: tuple[_MatchData, ...],
        has_registration: bool,
        has_classification: bool,
    ) -> None:
        self._storage = storage
        self._closed = False
        self._manifest = manifest
        self._metadata = metadata
        self._project = project
        self._stainings = tuple(Staining(self, item) for item in stainings)
        self._animals = tuple(Animal(self, item) for item in animals)
        self._slices = tuple(Slice(self, item) for item in slices)
        self._brain_regions = brain_regions
        self._images_by_slice = {
            slice_id: tuple(Image(self, image) for image in images)
            for slice_id, images in images_by_slice.items()
        }
        self._atlas = atlas
        self._registration = (
            Registration(self, atlas, atlas_registrations, detail_transforms)
            if has_registration and atlas is not None
            else None
        )
        self._classification = (
            ClassificationModule(self, classifications, matches)
            if has_classification
            else None
        )

    def _display_items(self) -> tuple[tuple[str, object], ...]:
        return (
            ("name", self._project.name),
            ("id", self._manifest.project.id),
            ("version", self._manifest.export_version),
            ("animals", len(self._animals)),
            ("slices", len(self._slices)),
            ("stainings", len(self._stainings)),
            (
                "modules",
                tuple(module.value for module in self._manifest.included_modules),
            ),
            ("closed", self._closed),
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise ClosedExportError("export is closed")

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def members(self) -> frozenset[str]:
        self._ensure_open()
        return self._storage.members

    def member(self, path: str) -> FileArtifact:
        """Get a raw archive member as a file artifact."""

        self._ensure_open()
        if path not in self.members:
            raise ObjectNotFoundError(f"member not found: {path}")
        return FileArtifact(self, path)

    @property
    def manifest(self) -> Manifest:
        self._ensure_open()
        return self._manifest

    @property
    def metadata(self) -> ExportMetadata:
        self._ensure_open()
        return self._metadata

    @property
    def project(self) -> ProjectMetadata:
        self._ensure_open()
        return self._project

    @property
    def stainings(self) -> tuple[Staining, ...]:
        self._ensure_open()
        return self._stainings

    @property
    def animals(self) -> tuple[Animal, ...]:
        self._ensure_open()
        return self._animals

    @property
    def slices(self) -> tuple[Slice, ...]:
        self._ensure_open()
        return self._slices

    @property
    def brain_regions(self) -> tuple[BrainRegion, ...]:
        self._ensure_open()
        return self._brain_regions

    @property
    def atlas(self) -> Atlas | None:
        self._ensure_open()
        return self._atlas

    @property
    def registration(self) -> Registration | None:
        self._ensure_open()
        return self._registration

    @property
    def classification(self) -> ClassificationModule | None:
        self._ensure_open()
        return self._classification

    @property
    def id(self) -> str:
        return self.manifest.project.id

    @property
    def version(self) -> str:
        return self.manifest.export_version

    @property
    def exported_at(self) -> datetime:
        return self.manifest.exported_at

    @property
    def name(self) -> str:
        return self.project.name

    def animal(self, animal_id: str) -> Animal:
        return _one(
            tuple(item for item in self.animals if item.id == animal_id),
            "animal",
            animal_id,
        )

    def animal_by_name(self, name: str) -> Animal:
        return _one(
            tuple(item for item in self.animals if item.name == name),
            "animal name",
            name,
        )

    def staining(self, staining_id: str) -> Staining:
        return _one(
            tuple(item for item in self.stainings if item.id == staining_id),
            "staining",
            staining_id,
        )

    def staining_by_name(self, name: str) -> Staining:
        return _one(
            tuple(item for item in self.stainings if item.name == name),
            "staining name",
            name,
        )

    def find_stainings(self, name: str | None = None) -> tuple[Staining, ...]:
        """Find canonical staining names using a case/punctuation-insensitive alias."""

        if name is None:
            return self.stainings
        alias = "".join(
            character for character in name.casefold() if character.isalnum()
        )
        return tuple(
            item
            for item in self.stainings
            if "".join(
                character for character in item.name.casefold() if character.isalnum()
            )
            == alias
        )

    def slice(self, slice_id: str) -> Slice:
        return _one(
            tuple(item for item in self.slices if item.id == slice_id),
            "slice",
            slice_id,
        )

    def find_slices(self, *, name: str | None = None) -> tuple[Slice, ...]:
        return tuple(item for item in self.slices if name is None or item.name == name)

    def brain_region(self, structure_id: int) -> BrainRegion:
        return _one(
            tuple(
                item for item in self.brain_regions if item.structure_id == structure_id
            ),
            "brain region",
            structure_id,
        )

    def find_brain_regions(
        self, *, name: str | None = None, acronym: str | None = None
    ) -> tuple[BrainRegion, ...]:
        return tuple(
            item
            for item in self.brain_regions
            if (name is None or item.name == name)
            and (acronym is None or item.acronym == acronym)
        )

    def close(self) -> None:
        if not self._closed:
            self._storage.close()
            self._closed = True

    def __enter__(self) -> ProjectExport:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
