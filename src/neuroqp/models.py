"""Stable public records for NeuroQP exports."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
)


def _parse_datetime(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    return value


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


NormalizedDatetime = Annotated[
    datetime,
    BeforeValidator(_parse_datetime),
    AfterValidator(_as_utc),
]


class Record(BaseModel):
    """Base for immutable records that preserve additive wire fields."""

    model_config = ConfigDict(extra="allow", frozen=True, populate_by_name=True)


class Module(StrEnum):
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
    """Describe the atlas selected for the exported project.

    Attributes
    ----------
    id
        Opaque atlas identifier.
    key
        Stable atlas family key.
    version
        Atlas data version.
    name
        Human-readable atlas name.
    species
        Species described by the atlas.
    plane
        Sectioning plane, such as ``"coronal"``.
    specification
        Additive atlas specification supplied by NeuroQP.
    """

    species: str
    plane: str
    specification: dict[str, Any]


class ManifestProject(Record):
    """Project identity embedded in the root manifest."""

    id: str
    slug: str
    name: str


class Manifest(Record):
    """Describe the identity and included content of a v2 export.

    Attributes
    ----------
    export_version
        Export format version. It is ``"v2"`` for this model.
    export_id
        Opaque identifier for this export snapshot.
    exported_at
        Snapshot creation time as a timezone-aware UTC datetime.
    project
        Project identifier, slug, and name recorded by the exporter.
    project_metadata_path
        Archive path to the export metadata record.
    included_modules
        Modules actually included in the export.
    atlas
        Atlas identity when the project has an atlas, otherwise ``None``.
    selected_classifier_head_ids_by_staining
        Mapping from staining IDs to selected classifier IDs.
    linked_training_run_ids_by_staining
        Mapping from staining IDs to linked training-run IDs or ``None``.
    """

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
    """Describe how and when an export snapshot was requested.

    Attributes
    ----------
    export_version
        Export format version.
    exported_at
        Snapshot creation time as a timezone-aware UTC datetime.
    export_id
        Opaque identifier matching :attr:`Manifest.export_id`.
    project_id
        Opaque project identifier.
    expires_at
        Expiry time of the source export request.
    requested_modules
        Modules requested when the export was created.
    selected_classifier_head_ids_by_staining
        Mapping from staining IDs to selected classifier IDs.
    """

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
    """Describe the project's image scales and annotations.

    Attributes
    ----------
    name
        Human-readable project name.
    type
        Project imaging type recorded by NeuroQP.
    atlas_id
        Selected atlas identifier, or ``None``.
    whole_slice_label
        Display label for whole-slice images.
    whole_slice_microns_per_pixel
        Whole-slice image pixel size in micrometres per pixel.
    detail_image_label
        Display label for detail images.
    detail_microns_per_pixel
        Detail-image pixel size in micrometres per pixel.
    comments
        Project comments, or ``None``.
    """

    name: str
    type: str
    atlas_id: str | None = Field(alias="atlasId")
    whole_slice_label: str = Field(alias="wholeSliceLabel")
    whole_slice_microns_per_pixel: float = Field(alias="wholeSliceMicronsPerPixel")
    detail_image_label: str = Field(alias="detailImageLabel")
    detail_microns_per_pixel: float = Field(alias="detailMicronsPerPixel")
    comments: str | None


class Staining(Record):
    """Store the identifier and human-readable name of one staining."""

    id: str = Field(alias="_id")
    name: str


class Animal(Record):
    """Describe one experimental animal.

    Attributes
    ----------
    id
        Opaque animal identifier.
    name
        Human-readable animal name.
    comments
        Animal comments, or ``None``.
    sex
        Recorded sex value, or ``None``.
    group
        Resolved experimental group name, or ``None``.
    condition
        Resolved experimental condition name, or ``None``.
    """

    id: str = Field(alias="_id")
    name: str
    comments: str | None
    sex: str | None
    group: str | None
    condition: str | None


class Slice(Record):
    """Describe one tissue slice.

    Attributes
    ----------
    id
        Opaque slice identifier.
    animal_id
        Identifier of the parent animal.
    slice_coordinate_mm
        Anterior-posterior coordinate in millimetres.
    name
        Human-readable slice name, or ``None``.
    """

    id: str = Field(alias="_id")
    animal_id: str = Field(alias="animalId")
    slice_coordinate_mm: float = Field(alias="apMm")
    name: str | None = None

    @property
    def ap_mm(self) -> float:
        """Backward-compatible name for the AP coordinate."""

        return self.slice_coordinate_mm


class BrainRegion(Record):
    """Identify an atlas brain region selected in the project.

    Attributes
    ----------
    structure_id
        Numeric structure identifier assigned by the atlas.
    name
        Full region name.
    acronym
        Atlas region acronym.
    """

    structure_id: int = Field(alias="structureId")
    name: str
    acronym: str


class Image(Record):
    """Describe one image stored in an export.

    Attributes
    ----------
    id
        Opaque image identifier.
    archive_path
        Root-relative path of the image inside the export.
    height, width
        Image dimensions in pixels.
    staining_id
        Identifier of the image staining.
    slice_id
        Identifier of the parent slice.
    magnification
        Magnification label recorded by NeuroQP.
    original_filename
        Filename recorded when the image was uploaded.
    """

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
    """Describe the atlas landmarks for one slice.

    Attributes
    ----------
    slice_id
        Identifier of the registered slice.
    slice_coordinate_mm
        Registered anterior-posterior coordinate in millimetres.
    landmarks
        Corresponding image-pixel and atlas-plane points.
    """

    slice_id: str
    slice_coordinate_mm: float
    landmarks: tuple[RegistrationLandmark, ...]


class DetailTransform(Record):
    """Describe a detail image's footprint in whole-slice pixel coordinates.

    Attributes
    ----------
    slice_id
        Identifier of the transformed slice.
    corners
        Ordered detail-image corners expressed as whole-slice ``(x, y)`` pixels.
    """

    slice_id: str
    corners: tuple[Point, ...]


from ._classification_models import (  # noqa: E402
    ClassificationResultInfo,
    ClassifierMetadata,
    DetectionSource,
    ExportLimits,
    IndependentDetectionSource,
    MatchResultInfo,
    MatchSide,
    SampleCounts,
    SharedDetectionSource,
    SliceExclusion,
    TrainingRun,
    TrainingSample,
    TrainingSummary,
    ValidationIssue,
    ValidationReport,
)

__all__ = [
    "Animal",
    "Atlas",
    "AtlasRegistration",
    "AtlasSummary",
    "BrainRegion",
    "ClassificationResultInfo",
    "ClassifierMetadata",
    "DetailTransform",
    "DetectionSource",
    "EntityReference",
    "ExportLimits",
    "ExportMetadata",
    "Image",
    "IndependentDetectionSource",
    "Manifest",
    "ManifestProject",
    "MatchResultInfo",
    "MatchSide",
    "Module",
    "NormalizedDatetime",
    "Point",
    "ProjectMetadata",
    "Record",
    "RegistrationLandmark",
    "SampleCounts",
    "SharedDetectionSource",
    "Slice",
    "SliceExclusion",
    "Staining",
    "TrainingRun",
    "TrainingSample",
    "TrainingSummary",
    "ValidationIssue",
    "ValidationReport",
]
