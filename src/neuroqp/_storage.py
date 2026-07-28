"""Safe, extraction-free access to ZIP and directory exports."""

from __future__ import annotations

import stat
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath

from .models import ExportLimits, ValidationIssue


class StorageError(Exception):
    """Internal storage failure carrying structured issues."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues


def _issue(path: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(path=path, code=code, message=message)


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not (
        "\\" in name
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    )


class Storage(ABC):
    """Common storage interface."""

    members: frozenset[str]

    @abstractmethod
    def read(self, member: str, max_bytes: int | None = None) -> bytes:
        """Read a member without extracting it."""

    @abstractmethod
    def close(self) -> None:
        """Release storage resources."""


class DirectoryStorage(Storage):
    """Safely read an extracted export directory."""

    def __init__(self, root: Path, limits: ExportLimits) -> None:
        self._root = root.resolve()
        issues: list[ValidationIssue] = []
        members: list[str] = []
        for path in root.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                issues.append(
                    _issue(relative, "unsafe_link", "symbolic links are not allowed")
                )
                continue
            if not path.is_file():
                continue
            if not _safe_member(relative):
                issues.append(
                    _issue(relative, "unsafe_path", "member path is not root-relative")
                )
                continue
            members.append(relative)
        if len(members) > limits.max_members:
            issues.append(
                _issue(
                    ".",
                    "member_limit",
                    f"directory contains more than {limits.max_members} files",
                )
            )
        if issues:
            raise StorageError(issues)
        self.members = frozenset(members)

    def read(self, member: str, max_bytes: int | None = None) -> bytes:
        if member not in self.members:
            raise FileNotFoundError(member)
        path = (self._root / member).resolve()
        if self._root not in path.parents:
            raise StorageError(
                [_issue(member, "unsafe_path", "member resolves outside export root")]
            )
        if max_bytes is not None and path.stat().st_size > max_bytes:
            raise StorageError(
                [_issue(member, "metadata_limit", f"member exceeds {max_bytes} bytes")]
            )
        return path.read_bytes()

    def close(self) -> None:
        """Directory storage owns no open resources."""


class ZipStorage(Storage):
    """Safely read a ZIP export without extraction."""

    def __init__(self, path: Path, limits: ExportLimits) -> None:
        try:
            archive = zipfile.ZipFile(path)
        except (OSError, zipfile.BadZipFile) as error:
            raise StorageError(
                [_issue(str(path), "invalid_container", f"cannot open ZIP: {error}")]
            ) from error

        issues: list[ValidationIssue] = []
        infos: dict[str, zipfile.ZipInfo] = {}
        total = 0
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if not _safe_member(name):
                issues.append(
                    _issue(name, "unsafe_path", "ZIP member path is not root-relative")
                )
                continue
            if name in infos:
                issues.append(
                    _issue(name, "duplicate_member", "ZIP member name is duplicated")
                )
                continue
            mode = info.external_attr >> 16
            if stat.S_IFMT(mode) == stat.S_IFLNK:
                issues.append(
                    _issue(name, "unsafe_link", "ZIP symbolic links are not allowed")
                )
                continue
            infos[name] = info
            total += info.file_size
            compressed = max(info.compress_size, 1)
            if info.file_size / compressed > limits.max_compression_ratio:
                issues.append(
                    _issue(
                        name,
                        "compression_limit",
                        "ZIP member exceeds the configured compression ratio",
                    )
                )
        if len(infos) > limits.max_members:
            issues.append(
                _issue(
                    str(path),
                    "member_limit",
                    f"ZIP contains more than {limits.max_members} members",
                )
            )
        if total > limits.max_total_uncompressed_bytes:
            issues.append(
                _issue(
                    str(path),
                    "size_limit",
                    "ZIP declared uncompressed size exceeds the configured limit",
                )
            )
        if issues:
            archive.close()
            raise StorageError(issues)
        self._archive = archive
        self._infos = infos
        self.members = frozenset(infos)

    def read(self, member: str, max_bytes: int | None = None) -> bytes:
        info = self._infos.get(member)
        if info is None:
            raise FileNotFoundError(member)
        if max_bytes is not None and info.file_size > max_bytes:
            raise StorageError(
                [_issue(member, "metadata_limit", f"member exceeds {max_bytes} bytes")]
            )
        try:
            with self._archive.open(info) as stream:
                data = (
                    stream.read() if max_bytes is None else stream.read(max_bytes + 1)
                )
        except (OSError, zipfile.BadZipFile, RuntimeError) as error:
            raise StorageError(
                [_issue(member, "corrupt_member", f"cannot read ZIP member: {error}")]
            ) from error
        if max_bytes is not None and len(data) > max_bytes:
            raise StorageError(
                [_issue(member, "metadata_limit", f"member exceeds {max_bytes} bytes")]
            )
        return data

    def close(self) -> None:
        self._archive.close()


def open_storage(path: Path, limits: ExportLimits) -> Storage:
    """Open a ZIP or directory export."""

    if path.is_dir():
        return DirectoryStorage(path, limits)
    if path.is_file():
        return ZipStorage(path, limits)
    raise StorageError([_issue(str(path), "not_found", "export path does not exist")])
