"""Stable public records for NeuroQP exports."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Record(BaseModel):
    """Base for immutable records that preserve additive wire fields."""

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        populate_by_name=True,
    )


class Module(str, Enum):
    """Optional v2 export modules."""

    DATA = "data"
    REGISTRATION = "registration"
    CLASSIFICATION = "classification"


class AtlasSummary(Record):
    """Atlas identity embedded in the root manifest."""

    id: str
    key: str
    version: str
    name: str


class ManifestProject(Record):
    """Project identity embedded in the root manifest."""

    id: str
    slug: str
    name: str


class Manifest(Record):
    """Root v2 export manifest."""

    export_version: Literal["v2"] = Field(alias="exportVersion")
    export_id: str = Field(alias="exportId")
    exported_at: datetime = Field(alias="exportedAt")
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
    exported_at: datetime = Field(alias="exportedAt")
    export_id: str = Field(alias="exportId")
    project_id: str = Field(alias="projectId")
    expires_at: datetime = Field(alias="expiresAt")
    requested_modules: tuple[Module, ...] = Field(alias="requestedModules")
    selected_classifier_head_ids_by_staining: dict[str, str] = Field(
        alias="selectedClassifierHeadIdsByStaining"
    )

    @field_validator("expires_at", mode="before")
    @classmethod
    def parse_milliseconds(cls, value: Any) -> Any:
        """Normalize exporter millisecond timestamps to UTC."""

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        return value


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
    ap_mm: float = Field(alias="apMm")
    name: str | None = None


class BrainRegion(Record):
    """Selected atlas brain region."""

    structure_id: int = Field(alias="structureId")
    name: str
    acronym: str


class Image(Record):
    """Canonical v2 image metadata."""

    image_id: str = Field(alias="imageId")
    archive_path: str = Field(alias="archivePath")
    height: int
    width: int
    staining_id: str = Field(alias="stainingId")
    slice_id: str = Field(alias="sliceId")
    magnification: str
    original_filename: str = Field(alias="originalFilename")


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
