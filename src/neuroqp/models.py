"""Stable public records for NeuroQP exports."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
)


def _parse_datetime(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    return value


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


NormalizedDatetime = Annotated[
    datetime,
    BeforeValidator(_parse_datetime),
    AfterValidator(_as_utc),
]


class Record(BaseModel):
    """Base for immutable records that preserve additive wire fields."""

    model_config = ConfigDict(extra="allow", frozen=True, populate_by_name=True)


class Module(str, Enum):
    """Optional v2 export modules."""

    DATA = "data"
    REGISTRATION = "registration"
    CLASSIFICATION = "classification"


class EntityReference(Record):
    """An exported object identity."""

    id: str
    name: str = Field(validation_alias=AliasChoices("name", "displayName"))


class AtlasSummary(Record):
    """Atlas identity embedded in the root manifest."""

    id: str
    key: str
    version: str
    name: str


class Atlas(AtlasSummary):
    """Normalized exported atlas metadata."""

    species: str
    plane: str
    specification: dict[str, Any]


class ManifestProject(Record):
    """Project identity embedded in the root manifest."""

    id: str
    slug: str
    name: str


class Manifest(Record):
    """Root v2 export manifest."""

    export_version: Literal["v2"] = Field(alias="exportVersion")
    export_id: str = Field(alias="exportId")
    exported_at: NormalizedDatetime = Field(alias="exportedAt")
    project: ManifestProject
    project_metadata_path: str = Field(alias="projectMetadataPath")
    included_modules: tuple[Module, ...] = Field(alias="includedModules")
    atlas: AtlasSummary | None
    selected_classifier_head_ids_by_staining: dict[str, str] = Field(
        alias="selectedClassifierHeadIdsByStaining"
    )
    linked_training_run_ids_by_staining: dict[str, str | None] = Field(
        alias="linkedTrainingRunIdsByStaining"
    )


class ExportMetadata(Record):
    """Metadata stored in ``project/export.json``."""

    export_version: Literal["v2"] = Field(alias="exportVersion")
    exported_at: NormalizedDatetime = Field(alias="exportedAt")
    export_id: str = Field(alias="exportId")
    project_id: str = Field(alias="projectId")
    expires_at: NormalizedDatetime = Field(alias="expiresAt")
    requested_modules: tuple[Module, ...] = Field(alias="requestedModules")
    selected_classifier_head_ids_by_staining: dict[str, str] = Field(
        alias="selectedClassifierHeadIdsByStaining"
    )


class ProjectMetadata(Record):
    """Project imaging metadata."""

    name: str
    type: str
    atlas_id: str | None = Field(alias="atlasId")
    whole_slice_label: str = Field(alias="wholeSliceLabel")
    whole_slice_microns_per_pixel: float = Field(alias="wholeSliceMicronsPerPixel")
    detail_image_label: str = Field(alias="detailImageLabel")
    detail_microns_per_pixel: float = Field(alias="detailMicronsPerPixel")
    comments: str | None


class Staining(Record):
    """Staining identity."""

    id: str = Field(alias="_id")
    name: str


class Animal(Record):
    """Animal metadata."""

    id: str = Field(alias="_id")
    name: str
    comments: str | None
    sex: str | None
    group: str | None
    condition: str | None


class Slice(Record):
    """Slice metadata."""

    id: str = Field(alias="_id")
    animal_id: str = Field(alias="animalId")
    slice_coordinate_mm: float = Field(alias="apMm")
    name: str | None = None

    @property
    def ap_mm(self) -> float:
        """Backward-compatible name for the AP coordinate."""

        return self.slice_coordinate_mm


class BrainRegion(Record):
    """Selected atlas brain region."""

    structure_id: int = Field(alias="structureId")
    name: str
    acronym: str


class Image(Record):
    """Canonical v2 image metadata."""

    id: str = Field(alias="imageId")
    archive_path: str = Field(alias="archivePath")
    height: int
    width: int
    staining_id: str = Field(alias="stainingId")
    slice_id: str = Field(alias="sliceId")
    magnification: str
    original_filename: str = Field(alias="originalFilename")

    @property
    def image_id(self) -> str:
        """Backward-compatible image ID name."""

        return self.id


class Point(Record):
    """A two-dimensional point."""

    x: float
    y: float


class RegistrationLandmark(Record):
    """Corresponding image and atlas-plane coordinates."""

    image: Point
    atlas_plane_mm: Point


class AtlasRegistration(Record):
    """Normalized atlas registration for one slice."""

    slice_id: str
    slice_coordinate_mm: float
    landmarks: tuple[RegistrationLandmark, ...]


class DetailTransform(Record):
    """Detail-image footprint in whole-slice pixel coordinates."""

    slice_id: str
    corners: tuple[Point, ...]


class SliceExclusion(Record):
    """A documented reason why one slice has no result."""

    slice_id: str = Field(alias="sliceId")
    slice_name: str | None = Field(alias="sliceName")
    reason_code: str = Field(alias="reasonCode")
    reason: str


class ClassifierMetadata(Record):
    """Metadata for an exported classifier."""

    id: str
    display_name: str = Field(alias="displayName")
    version: int
    head_type: str = Field(alias="headType")
    source: Literal["trained", "platform_import", "project_import"]
    created_at: NormalizedDatetime = Field(alias="createdAt")
    comments: str | None
    staining: EntityReference
    training_run_id: str | None = Field(alias="trainingRunId")
    evaluation_metrics: dict[str, Any] = Field(alias="evaluationMetrics")


class SampleCounts(Record):
    """On/off sample counts."""

    on: int
    off: int
    total: int
    slice_count: int | None = Field(default=None, alias="sliceCount")


class TrainingRun(Record):
    """Exported classifier training-run summary."""

    id: str
    status: str
    training_duration_ms: float = Field(alias="trainingDurationMs")
    final_metrics: dict[str, float | int] = Field(alias="finalMetrics")
    recorded_sample_counts: SampleCounts = Field(alias="recordedSampleCounts")
    histories: dict[str, tuple[float, ...]]
    coverage: dict[str, Any] | None = None
    confidence: dict[str, Any] | None = None
    convergence: dict[str, Any] | None = None


class TrainingSummary(Record):
    """Training data and run summary for one staining."""

    staining: EntityReference
    sample_basis: Literal["current_at_export"] = Field(alias="sampleBasis")
    current_samples: SampleCounts = Field(alias="currentSamples")
    training_run: TrainingRun | None = Field(alias="trainingRun")


class TrainingSample(Record):
    """One exported classifier training sample."""

    slice_id: str = Field(alias="sliceId")
    slice_name: str | None = Field(alias="sliceName")
    staining_id: str = Field(alias="stainingId")
    staining_name: str = Field(alias="stainingName")
    cell_id: int | None = Field(alias="cellId")
    cell_detection_run_id: str | None = Field(default=None, alias="cellDetectionRunId")
    label: Literal["on", "off"]
    created_at: NormalizedDatetime = Field(alias="createdAt")


class SharedDetectionSource(Record):
    """Classification lineage using a shared cell-count detection."""

    kind: Literal["shared_detection"] = "shared_detection"
    cell_count_id: str = Field(alias="cellCountId")


class IndependentDetectionSource(Record):
    """Classification lineage using a staining-specific detection."""

    kind: Literal["independent_detection"] = "independent_detection"
    cell_detection_run_id: str = Field(alias="cellDetectionRunId")


DetectionSource = Annotated[
    SharedDetectionSource | IndependentDetectionSource,
    Field(discriminator="kind"),
]


class ClassificationResultInfo(Record):
    """Index metadata for one classification result."""

    slice_id: str = Field(alias="sliceId")
    slice_name: str | None = Field(alias="sliceName")
    staining_id: str = Field(alias="stainingId")
    classifier_id: str = Field(alias="classifierId")
    source: DetectionSource = Field(alias="sourceLineage")
    on_count: int | None = Field(alias="onCount")
    off_count: int | None = Field(alias="offCount")
    threshold: float | None
    timestamp: NormalizedDatetime
    npz_path: str = Field(alias="npzPath")


class MatchSide(Record):
    """One side of an exported cell match."""

    staining: EntityReference
    detection_run_id: str = Field(alias="detectionRunId")
    unmatched_count: int | None = Field(alias="unmatchedCount")


class MatchResultInfo(Record):
    """Index metadata for one per-slice match result."""

    slice_id: str = Field(alias="sliceId")
    slice_name: str | None = Field(alias="sliceName")
    side_a: MatchSide = Field(alias="sideA")
    side_b: MatchSide = Field(alias="sideB")
    algorithm_version: str = Field(alias="algorithmVersion")
    overlap_threshold: float = Field(alias="overlapThreshold")
    timestamp: NormalizedDatetime
    candidate_pair_count: int | None = Field(alias="candidatePairCount")
    matched_count: int | None = Field(alias="matchedCount")
    npz_path: str = Field(alias="npzPath")


class ValidationIssue(Record):
    """One actionable export validation issue."""

    path: str
    code: str
    message: str
    field: str | None = None


class ValidationReport(Record):
    """Aggregate export validation result."""

    issues: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        """Whether the export passed validation."""

        return not self.issues


class ExportLimits(Record):
    """Configurable resource limits; path and pickle protections remain mandatory."""

    max_members: int = 10_000
    max_total_uncompressed_bytes: int = 4 * 1024**3
    max_metadata_bytes: int = 8 * 1024**2
    max_compression_ratio: float = 1_000

    @field_validator(
        "max_members",
        "max_total_uncompressed_bytes",
        "max_metadata_bytes",
    )
    @classmethod
    def positive_integer(cls, value: int) -> int:
        """Require useful positive limits."""

        if value <= 0:
            raise ValueError("limit must be positive")
        return value

    @field_validator("max_compression_ratio")
    @classmethod
    def positive_ratio(cls, value: float) -> float:
        """Require a useful positive ratio."""

        if value <= 0:
            raise ValueError("limit must be positive")
        return value
