"""Root project export and lookup API."""

from __future__ import annotations

from datetime import datetime

from ._classification import ClassificationModule, _ClassificationData, _MatchData
from ._objects import (
    Animal,
    FileArtifact,
    Image,
    Registration,
    Slice,
    Staining,
    _Display,
    _one,
)
from ._storage import Storage
from .errors import ClosedExportError, ObjectNotFoundError
from .models import Animal as AnimalMetadata
from .models import (
    Atlas,
    AtlasRegistration,
    BrainRegion,
    DetailTransform,
    ExportMetadata,
    Manifest,
    ProjectMetadata,
)
from .models import Image as ImageMetadata
from .models import Slice as SliceMetadata
from .models import Staining as StainingMetadata


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
