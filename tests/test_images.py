from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import numpy as np
import pytest
from tifffile import TiffFile, imread, imwrite

from neuroqp import ClosedExportError, ExportLimits, open_export

FIXTURES = Path(__file__).parent / "fixtures"
VALID = FIXTURES / "minimal-v2"
IMAGE_MEMBER = "data/slices/slice-1/images/image-1__minimal.tif"


def _tiff_export(tmp_path: Path) -> tuple[Path, np.ndarray]:
    root = tmp_path / "export"
    shutil.copytree(VALID, root)
    pixels = np.arange(12 * 16, dtype=np.uint16).reshape(12, 16)
    imwrite(root / IMAGE_MEMBER, pixels, compression="lzw", rowsperstrip=4)
    return root, pixels


def _zip_export(source: Path, target: Path) -> Path:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())
    return target


def test_large_directory_artifact_is_streamed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "export"
    shutil.copytree(VALID, root)
    large = root / "large.bin"
    size = 5 * 1024**3
    with large.open("wb") as writer:
        writer.truncate(size)

    def reject_read_bytes(_path: Path) -> bytes:
        raise AssertionError("artifact access must not call Path.read_bytes()")

    monkeypatch.setattr(Path, "read_bytes", reject_read_bytes)
    limits = ExportLimits(max_total_uncompressed_bytes=1)
    with open_export(root, limits=limits) as export:
        artifact = export.member("large.bin")
        assert artifact.size_bytes == size
        with artifact.open() as reader:
            assert reader.read(1) == b"\0"
            reader.seek(-1, 2)
            assert reader.read(1) == b"\0"
        with artifact.as_path() as path:
            assert path == large.resolve()


@pytest.mark.parametrize("as_zip", [False, True])
def test_tiff_access_methods(tmp_path: Path, as_zip: bool) -> None:
    root, expected = _tiff_export(tmp_path)
    source = _zip_export(root, tmp_path / "export.zip") if as_zip else root
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    with open_export(source) as export:
        image = export.slices[0].images[0]
        assert image.size_bytes == (root / IMAGE_MEMBER).stat().st_size

        with image.open() as stream, TiffFile(stream) as tif:
            page = tif.pages[0]
            assert page.shape == expected.shape
            assert page.dtype == expected.dtype
            assert page.compression == 5
            assert len(tuple(page.segments())) == 3

        with image.open() as stream:
            np.testing.assert_array_equal(imread(stream), expected)

        with image.as_path(directory=scratch) as path:
            materialized = path
            assert path.suffix == ".tif"
            assert path.exists()
            if as_zip:
                assert scratch in path.parents
            else:
                assert path == (root / IMAGE_MEMBER).resolve()

            selection = imread(path, selection=(slice(2, 6), slice(3, 8)))
            np.testing.assert_array_equal(selection, expected[2:6, 3:8])

            decoded_path = tmp_path / "decoded.memmap"
            with TiffFile(path) as tif:
                decoded = tif.pages[0].asarray(out=str(decoded_path))
            assert isinstance(decoded, np.memmap)
            np.testing.assert_array_equal(decoded, expected)
            decoded.flush()
            del decoded

        assert materialized.exists() == (not as_zip)


def test_artifact_access_requires_open_export(tmp_path: Path) -> None:
    root, _ = _tiff_export(tmp_path)
    export = open_export(root)
    image = export.slices[0].images[0]
    artifact = export.member(IMAGE_MEMBER)
    export.close()

    with pytest.raises(ClosedExportError):
        image.open()
    with pytest.raises(ClosedExportError):
        _ = image.size_bytes
    with pytest.raises(ClosedExportError), image.as_path():
        pass
    with pytest.raises(ClosedExportError):
        artifact.open()
    with pytest.raises(ClosedExportError):
        _ = artifact.size_bytes
    with pytest.raises(ClosedExportError), artifact.as_path():
        pass
