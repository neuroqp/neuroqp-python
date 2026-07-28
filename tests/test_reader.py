from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from neuroqp import (
    ClosedExportError,
    ExportLimits,
    InvalidExportError,
    UnsupportedVersionError,
    open_export,
    validate_export,
)

FIXTURES = Path(__file__).parent / "fixtures"
VALID = FIXTURES / "minimal-v2"


def make_zip(source: Path, target: Path) -> Path:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(
                    path.relative_to(source).as_posix(),
                    date_time=(2026, 7, 28, 12, 0, 0),
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    return target


@pytest.mark.parametrize("as_zip", [False, True])
def test_open_export_reads_typed_metadata(tmp_path: Path, as_zip: bool) -> None:
    source = make_zip(VALID, tmp_path / "minimal.zip") if as_zip else VALID
    with open_export(source) as export:
        assert export.version == "v2"
        assert export.id == "project-1"
        assert export.name == "Minimal project"
        assert export.project.detail_microns_per_pixel == 1.719
        assert export.animals[0].group == "control"
        assert export.slices[0].animal_id == export.animals[0].id
        assert export.stainings[0].name == "DAPI"
        assert export.brain_regions[0].structure_id == 599
        assert export.manifest.model_extra == {"futureField": "preserved"}
        assert export.metadata.expires_at.tzinfo is not None
    assert export.closed


def test_records_are_immutable() -> None:
    with open_export(VALID) as export, pytest.raises(ValidationError):
        export.project.name = "Changed"  # type: ignore[misc]


def test_closed_export_rejects_access() -> None:
    export = open_export(VALID)
    export.close()
    export.close()
    with pytest.raises(ClosedExportError):
        _ = export.project
    with pytest.raises(ClosedExportError):
        export.__enter__()


def test_validate_aggregates_missing_members() -> None:
    report = validate_export(FIXTURES / "invalid-v2")
    assert not report.valid
    assert len(report.issues) > 6
    assert {issue.code for issue in report.issues} == {
        "missing_member",
        "invalid_field",
    }


def test_open_invalid_export_raises() -> None:
    with pytest.raises(InvalidExportError) as caught:
        open_export(FIXTURES / "invalid-v2")
    assert caught.value.report.issues
    assert "issues" in str(caught.value)


def test_unsupported_version_has_specific_error(tmp_path: Path) -> None:
    copy = tmp_path / "export"
    shutil.copytree(VALID, copy)
    manifest = json.loads((copy / "manifest.json").read_text())
    manifest["exportVersion"] = "v3"
    (copy / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(UnsupportedVersionError):
        open_export(copy)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        (
            "archivePath",
            "data/slices/slice-1/images/minimal.tif",
            "invalid_archive_path",
        ),
        ("sliceId", "slice-2", "inconsistent_slice"),
        ("stainingId", "staining-2", "unknown_staining"),
    ],
)
def test_canonical_image_references_are_validated(
    tmp_path: Path,
    field: str,
    value: str,
    code: str,
) -> None:
    copy = tmp_path / "export"
    shutil.copytree(VALID, copy)
    path = copy / "data/slices/slice-1/images.json"
    images = json.loads(path.read_text())
    images[0][field] = value
    path.write_text(json.dumps(images))
    report = validate_export(copy)
    assert code in {issue.code for issue in report.issues}


def test_missing_referenced_image_is_invalid(tmp_path: Path) -> None:
    copy = tmp_path / "export"
    shutil.copytree(VALID, copy)
    (copy / "data/slices/slice-1/images/image-1__minimal.tif").unlink()
    report = validate_export(copy)
    assert "missing_member" in {issue.code for issue in report.issues}


def test_cross_file_invariants_are_validated(tmp_path: Path) -> None:
    copy = tmp_path / "export"
    shutil.copytree(VALID, copy)
    path = copy / "project/export.json"
    metadata = json.loads(path.read_text())
    metadata["projectId"] = "other"
    metadata["requestedModules"] = []
    path.write_text(json.dumps(metadata))
    slices_path = copy / "project/slices.json"
    slices = json.loads(slices_path.read_text())
    slices[0]["animalId"] = "missing"
    slices_path.write_text(json.dumps(slices))
    codes = {issue.code for issue in validate_export(copy).issues}
    assert {"inconsistent_reference", "unknown_animal"} <= codes


def test_invalid_json_and_utf8_are_reported(tmp_path: Path) -> None:
    copy = tmp_path / "export"
    shutil.copytree(VALID, copy)
    (copy / "project/project.json").write_text("{")
    (copy / "project/animals.json").write_bytes(b"\xff")
    codes = {issue.code for issue in validate_export(copy).issues}
    assert {"invalid_json", "invalid_utf8"} <= codes


def test_metadata_limit_can_be_overridden() -> None:
    report = validate_export(VALID, limits=ExportLimits(max_metadata_bytes=10))
    assert "metadata_limit" in {issue.code for issue in report.issues}


def test_missing_path_is_structured() -> None:
    report = validate_export("does-not-exist")
    assert report.issues[0].code == "not_found"


def test_bad_zip_is_structured(tmp_path: Path) -> None:
    path = tmp_path / "bad.zip"
    path.write_text("not a zip")
    report = validate_export(path)
    assert report.issues[0].code == "invalid_container"


@pytest.mark.parametrize(
    ("member", "code"),
    [
        ("../escape.json", "unsafe_path"),
        ("/absolute.json", "unsafe_path"),
        ("windows\\escape.json", "unsafe_path"),
    ],
)
def test_zip_rejects_unsafe_paths(tmp_path: Path, member: str, code: str) -> None:
    path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, "{}")
    assert validate_export(path).issues[0].code == code


def test_zip_rejects_duplicate_members(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.zip"
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        zipfile.ZipFile(path, "w") as archive,
    ):
        archive.writestr("manifest.json", "{}")
        archive.writestr("manifest.json", "{}")
    assert validate_export(path).issues[0].code == "duplicate_member"


def test_zip_member_and_total_limits(tmp_path: Path) -> None:
    path = tmp_path / "large.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("one", "x" * 100)
        archive.writestr("two", "y" * 100)
    report = validate_export(
        path,
        limits=ExportLimits(
            max_members=1,
            max_total_uncompressed_bytes=1,
            max_compression_ratio=1,
        ),
    )
    codes = {issue.code for issue in report.issues}
    assert {"member_limit", "size_limit", "compression_limit"} <= codes


def test_directory_rejects_symlink(tmp_path: Path) -> None:
    root = tmp_path / "export"
    root.mkdir()
    target = tmp_path / "outside"
    target.write_text("outside")
    try:
        (root / "manifest.json").symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are unavailable on this runner")
    assert validate_export(root).issues[0].code == "unsafe_link"


def test_duplicate_ids_and_images_are_reported(tmp_path: Path) -> None:
    copy = tmp_path / "export"
    shutil.copytree(VALID, copy)
    animals_path = copy / "project/animals.json"
    animals = json.loads(animals_path.read_text())
    animals.append(animals[0])
    animals_path.write_text(json.dumps(animals))
    images_path = copy / "data/slices/slice-1/images.json"
    images = json.loads(images_path.read_text())
    images.append(images[0])
    images_path.write_text(json.dumps(images))
    codes = {issue.code for issue in validate_export(copy).issues}
    assert {"duplicate_id", "duplicate_image"} <= codes


def test_slice_copy_must_match_project_collection(tmp_path: Path) -> None:
    copy = tmp_path / "export"
    shutil.copytree(VALID, copy)
    path = copy / "data/slices/slice-1/slice.json"
    slice_ = json.loads(path.read_text())
    slice_["apMm"] = 42
    path.write_text(json.dumps(slice_))
    assert "inconsistent_slice" in {
        issue.code for issue in validate_export(copy).issues
    }


def test_registration_manifest_is_validated(tmp_path: Path) -> None:
    copy = tmp_path / "export"
    shutil.copytree(VALID, copy)
    root_path = copy / "manifest.json"
    root = json.loads(root_path.read_text())
    root["includedModules"].append("registration")
    root["atlas"] = {
        "id": "atlas-1",
        "key": "atlas",
        "version": "v1",
        "name": "Atlas",
    }
    root_path.write_text(json.dumps(root))
    export_path = copy / "project/export.json"
    metadata = json.loads(export_path.read_text())
    metadata["requestedModules"].append("registration")
    export_path.write_text(json.dumps(metadata))
    atlas_path = copy / "registration/atlas/atlas-manifest.json"
    atlas_path.parent.mkdir(parents=True)
    atlas_path.write_text(
        json.dumps(
            {
                "id": "wrong",
                "key": "atlas",
                "version": "v1",
                "name": "Atlas",
                "species": "mouse",
                "plane": "coronal",
            }
        )
    )
    issues = validate_export(copy).issues
    assert {issue.code for issue in issues} == {
        "invalid_field",
        "inconsistent_atlas",
    }


def test_classification_manifest_paths_are_validated(tmp_path: Path) -> None:
    copy = tmp_path / "export"
    shutil.copytree(VALID, copy)
    root_path = copy / "manifest.json"
    root = json.loads(root_path.read_text())
    root["includedModules"].append("classification")
    root_path.write_text(json.dumps(root))
    export_path = copy / "project/export.json"
    metadata = json.loads(export_path.read_text())
    metadata["requestedModules"].append("classification")
    export_path.write_text(json.dumps(metadata))
    manifest_path = copy / "classification/manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "exportVersion": "v1",
                "stainings": [
                    "not-an-object",
                    {
                        "classifierPath": "missing",
                        "trainingSummaryPath": "missing",
                        "trainingSamplesPath": "missing",
                        "resultIndexPath": "missing",
                    },
                ],
                "matches": "not-an-array",
            }
        )
    )
    codes = {issue.code for issue in validate_export(copy).issues}
    assert {"unsupported_version", "invalid_field", "invalid_reference"} <= codes


def test_valid_empty_classification_manifest(tmp_path: Path) -> None:
    copy = tmp_path / "export"
    shutil.copytree(VALID, copy)
    root_path = copy / "manifest.json"
    root = json.loads(root_path.read_text())
    root["includedModules"].append("classification")
    root_path.write_text(json.dumps(root))
    export_path = copy / "project/export.json"
    metadata = json.loads(export_path.read_text())
    metadata["requestedModules"].append("classification")
    export_path.write_text(json.dumps(metadata))
    manifest_path = copy / "classification/manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"exportVersion": "v2", "stainings": [], "matches": []})
    )
    assert validate_export(copy).valid


def test_directory_member_limit() -> None:
    report = validate_export(VALID, limits=ExportLimits(max_members=1))
    assert report.issues[0].code == "member_limit"


def test_limit_values_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ExportLimits(max_members=0)
    with pytest.raises(ValidationError):
        ExportLimits(max_compression_ratio=0)


def test_zip_symlink_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "link.zip"
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = 0o120777 << 16
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, "target")
    assert validate_export(path).issues[0].code == "unsafe_link"
