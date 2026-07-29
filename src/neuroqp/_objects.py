"""Reader-bound project objects and display helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, NoReturn

from ._storage import StorageError
from .errors import AmbiguousNameError, InvalidExportError, ObjectNotFoundError
from .models import (
    Animal as AnimalMetadata,
)
from .models import (
    Atlas,
    AtlasRegistration,
    DetailTransform,
    ValidationIssue,
    ValidationReport,
)
from .models import Image as ImageMetadata
from .models import Slice as SliceMetadata
from .models import Staining as StainingMetadata

if TYPE_CHECKING:
    from ._project import ProjectExport


def _object_id(value: object) -> str:
    if isinstance(value, str):
        return value
    object_id = getattr(value, "id", None)
    if isinstance(object_id, str):
        return object_id
    raise TypeError("expected an object or ID string")


def _one[ItemT](items: tuple[ItemT, ...], label: str, value: object) -> ItemT:
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
        """Open the artifact as a binary stream.

        Returns
        -------
        BinaryIO
            A native file stream for an extracted export or a streaming ZIP
            member.

        Notes
        -----
        Close the stream before closing its parent export.
        """

        self._export._ensure_open()
        try:
            return self._export._storage.open(self.path)
        except (FileNotFoundError, StorageError) as error:
            _invalid(self.path, "unreadable_member", str(error))

    @property
    def size_bytes(self) -> int:
        """Encoded artifact size in bytes.

        This is the stored file size, not the memory required for decoded
        image pixels.
        """

        self._export._ensure_open()
        try:
            return self._export._storage.size(self.path)
        except (FileNotFoundError, OSError, StorageError) as error:
            _invalid(self.path, "unreadable_member", str(error))

    @contextmanager
    def as_path(
        self,
        *,
        directory: str | Path | None = None,
    ) -> Iterator[Path]:
        """Provide a filesystem path for the artifact.

        Parameters
        ----------
        directory
            Scratch directory used when a ZIP member must be copied.

        Returns
        -------
        AbstractContextManager[Path]
            A context manager yielding the original path for a directory export
            or a temporary copy for a ZIP export.

        Notes
        -----
        Use the path only inside this context and while the parent export is
        open. Temporary ZIP copies are removed when the context exits.
        """

        self._export._ensure_open()
        stack = ExitStack()
        try:
            path = stack.enter_context(
                self._export._storage.as_path(
                    self.path,
                    directory=directory,
                )
            )
        except (FileNotFoundError, OSError, StorageError) as error:
            stack.close()
            _invalid(self.path, "unreadable_member", str(error))
        with stack:
            yield path


class _Bound[MetadataT](_Display):
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

    @property
    def size_bytes(self) -> int:
        """Encoded image-file size in bytes."""

        return FileArtifact(self._export, self.metadata.archive_path).size_bytes

    def as_path(
        self,
        *,
        directory: str | Path | None = None,
    ) -> AbstractContextManager[Path]:
        """Provide the image as a filesystem path within a context manager."""

        return FileArtifact(self._export, self.metadata.archive_path).as_path(
            directory=directory
        )

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
