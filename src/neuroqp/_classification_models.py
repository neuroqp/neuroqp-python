"""Public records for classification, matching, and validation."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, field_validator

from .models import EntityReference, NormalizedDatetime, Record


class SliceExclusion(Record):
    """Explain why one slice has no classification or match result.

    Attributes
    ----------
    slice_id
        Identifier of the omitted slice.
    slice_name
        Human-readable slice name, or ``None``.
    reason_code
        Stable machine-readable omission category.
    reason
        Human-readable explanation recorded by the exporter.
    """

    slice_id: str = Field(alias="sliceId")
    slice_name: str | None = Field(alias="sliceName")
    reason_code: str = Field(alias="reasonCode")
    reason: str


class ClassifierMetadata(Record):
    """Describe the classifier selected for one staining.

    Attributes
    ----------
    id
        Opaque classifier-head identifier.
    display_name
        Human-readable classifier name.
    version
        Numeric classifier version.
    head_type
        Classifier-head type recorded by NeuroQP.
    source
        Whether the classifier was trained in this project or imported.
    created_at
        Creation time as a timezone-aware UTC datetime.
    comments
        Classifier comments, or ``None``.
    staining
        Staining identity associated with the classifier.
    training_run_id
        Linked training-run identifier, or ``None``.
    evaluation_metrics
        Additive evaluation metrics recorded for the classifier.
    """

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
    """Store positive, negative, total, and optional slice sample counts."""

    on: int
    off: int
    total: int
    slice_count: int | None = Field(default=None, alias="sliceCount")


class TrainingRun(Record):
    """Store the exported summary of one classifier training run."""

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
    """Summarize classifier training data for one staining.

    Attributes
    ----------
    staining
        Staining identity associated with the training data.
    sample_basis
        Basis of the sample counts; v2 records samples current at export time.
    current_samples
        Positive, negative, total, and slice counts at export time.
    training_run
        Linked training-run summary, or ``None`` when none was exported.
    """

    staining: EntityReference
    sample_basis: Literal["current_at_export"] = Field(alias="sampleBasis")
    current_samples: SampleCounts = Field(alias="currentSamples")
    training_run: TrainingRun | None = Field(alias="trainingRun")


class TrainingSample(Record):
    """Describe one positive or negative classifier training example.

    Attributes
    ----------
    slice_id, slice_name
        Identifier and optional display name of the source slice.
    staining_id, staining_name
        Identifier and display name of the classified staining.
    cell_id
        Cell label in the source detection mask, or ``None``.
    cell_detection_run_id
        Staining-specific detection-run identifier, or ``None``.
    label
        Exported training label, ``"on"`` or ``"off"``.
    created_at
        Sample creation time as a timezone-aware UTC datetime.
    """

    slice_id: str = Field(alias="sliceId")
    slice_name: str | None = Field(alias="sliceName")
    staining_id: str = Field(alias="stainingId")
    staining_name: str = Field(alias="stainingName")
    cell_id: int | None = Field(alias="cellId")
    cell_detection_run_id: str | None = Field(default=None, alias="cellDetectionRunId")
    label: Literal["on", "off"]
    created_at: NormalizedDatetime = Field(alias="createdAt")


class SharedDetectionSource(Record):
    """Identify classification based on a shared cell-count detection.

    Attributes
    ----------
    kind
        Always ``"shared_detection"``.
    cell_count_id
        Identifier of the shared cell-count result.
    """

    kind: Literal["shared_detection"] = "shared_detection"
    cell_count_id: str = Field(alias="cellCountId")


class IndependentDetectionSource(Record):
    """Identify classification based on a staining-specific detection.

    Attributes
    ----------
    kind
        Always ``"independent_detection"``.
    cell_detection_run_id
        Identifier of the staining-specific detection run.
    """

    kind: Literal["independent_detection"] = "independent_detection"
    cell_detection_run_id: str = Field(alias="cellDetectionRunId")


DetectionSource = Annotated[
    SharedDetectionSource | IndependentDetectionSource,
    Field(discriminator="kind"),
]


class ClassificationResultInfo(Record):
    """Describe one slice-level classification result before arrays are loaded.

    Attributes
    ----------
    slice_id, slice_name
        Identifier and optional display name of the classified slice.
    staining_id
        Identifier of the classified staining.
    classifier_id
        Identifier of the classifier used for this result.
    source
        Detection lineage that produced the classified cells.
    on_count, off_count
        Exported positive and negative counts, or ``None``.
    threshold
        Exported probability threshold, or ``None``.
    timestamp
        Result time as a timezone-aware UTC datetime.
    npz_path
        Archive path to the result arrays.
    """

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
    """Describe one staining and detection run in a cell match."""

    staining: EntityReference
    detection_run_id: str = Field(alias="detectionRunId")
    unmatched_count: int | None = Field(alias="unmatchedCount")


class MatchResultInfo(Record):
    """Describe one slice-level cell-match result before arrays are loaded.

    Attributes
    ----------
    slice_id, slice_name
        Identifier and optional display name of the matched slice.
    side_a, side_b
        Actual staining, detection-run, and unmatched count for each NPZ side.
    algorithm_version
        Matching algorithm version.
    overlap_threshold
        Minimum overlap fraction used to retain candidate pairs.
    timestamp
        Result time as a timezone-aware UTC datetime.
    candidate_pair_count
        Number of overlapping candidates considered, or ``None``.
    matched_count
        Number of retained one-to-one matches, or ``None``.
    npz_path
        Archive path to the match arrays.
    """

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
    """Describe one actionable problem found in an export.

    Attributes
    ----------
    path
        Root-relative member path associated with the problem.
    code
        Stable machine-readable issue code.
    message
        Human-readable explanation.
    field
        JSON field or NPZ array name, or ``None``.
    """

    path: str
    code: str
    message: str
    field: str | None = None


class ValidationReport(Record):
    """Collect all independently detectable metadata validation issues.

    Attributes
    ----------
    issues
        Validation issues. An empty tuple means the export is valid.
    valid
        ``True`` when :attr:`issues` is empty.
    """

    issues: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        """Whether the export passed validation."""

        return not self.issues


class ExportLimits(Record):
    """Configure resource limits for reading untrusted exports.

    Attributes
    ----------
    max_members
        Maximum number of archive members.
    max_total_uncompressed_bytes
        Maximum declared total uncompressed ZIP size in bytes. Extracted
        directories have no aggregate byte limit.
    max_metadata_bytes
        Maximum size of one JSON or JSONL metadata member in bytes.
    max_compression_ratio
        Maximum declared compression ratio of one ZIP member. This does not
        apply to extracted directories.

    Notes
    -----
    Path-safety and NumPy pickle protections remain mandatory.
    """

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
    def _positive_integer(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("limit must be positive")
        return value

    @field_validator("max_compression_ratio")
    @classmethod
    def _positive_ratio(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("limit must be positive")
        return value
