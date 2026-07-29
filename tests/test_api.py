from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from neuroqp import (
    AmbiguousNameError,
    ClosedExportError,
    InvalidExportError,
    ObjectNotFoundError,
    SharedDetectionSource,
    open_export,
    validate_export,
)
from neuroqp.cli import main
from tests.export_factory import MINIMAL, full_export, write_json


def test_object_graph_and_artifacts(tmp_path: Path) -> None:
    with open_export(full_export(tmp_path)) as export:
        animal = export.animal_by_name("Mouse 1")
        slice_ = animal.slices[0]
        image = slice_.image("image-1")
        assert export.animal(animal.id) is animal
        assert export.slice(slice_.id) is slice_
        assert export.staining("staining-1").name == "DAPI"
        assert export.staining_by_name("NeuN").id == "staining-2"
        assert export.find_stainings("d-a p_i") == (export.stainings[0],)
        assert export.find_stainings() == export.stainings
        assert export.find_slices(name="Slice 1") == (slice_,)
        assert export.brain_region(599).acronym == "CM"
        assert export.find_brain_regions(acronym="CM")[0].structure_id == 599
        assert slice_.animal is animal
        assert image.slice is slice_
        assert image.staining.name == "DAPI"
        assert image.metadata.archive_path.endswith("image-1__minimal.tif")
        assert slice_.find_images(staining="DAPI", magnification="10x") == (image,)
        assert slice_.find_images(filename="missing") == ()
        assert (
            image.open().read() == (MINIMAL / image.metadata.archive_path).read_bytes()
        )
        assert slice_.cell_mask is not None
        assert slice_.cell_mask.open().read() == b"mask"
        assert export.member("manifest.json").open().read().startswith(b"{")
        assert "manifest.json" in export.members
        with pytest.raises(ObjectNotFoundError):
            export.member("missing")
        with pytest.raises(ObjectNotFoundError):
            export.animal("missing")
        with pytest.raises(TypeError):
            slice_.find_images(staining=object())  # type: ignore[arg-type]


def test_reader_objects_have_concise_text_and_notebook_representations(
    tmp_path: Path,
) -> None:
    root = full_export(tmp_path)
    project_path = root / "project/project.json"
    project = json.loads(project_path.read_text())
    project["name"] = "Project <unsafe>"
    write_json(project_path, project)
    export = open_export(root)
    assert export.classification is not None
    assert export.registration is not None
    classification = export.classification.for_staining("DAPI")
    match = export.classification.match("dapi-neun")
    slice_registration = export.slices[0].registration
    assert slice_registration is not None
    objects = (
        export,
        export.animals[0],
        export.stainings[0],
        export.slices[0],
        export.slices[0].images[0],
        export.member("manifest.json"),
        export.registration,
        slice_registration,
        export.classification,
        classification,
        classification.load_result("slice-1"),
        classification.load_results(),
        match,
        match.load_result("slice-1"),
        match.load_results(),
    )
    for item in objects:
        assert repr(item).startswith(f"{type(item).__name__}(")
        assert str(item) == repr(item)
        assert "object at 0x" not in repr(item)
        assert "<table>" in item._repr_html_()
    assert "animals=1" in repr(export)
    assert "array(" not in repr(classification.load_results())
    assert "Project &lt;unsafe&gt;" in export._repr_html_()
    assert "Project <unsafe>" not in export._repr_html_()
    export.close()
    assert "closed=True" in repr(export)


def test_registration_api(tmp_path: Path) -> None:
    with open_export(full_export(tmp_path)) as export:
        assert export.atlas is not None
        assert export.registration is not None
        assert export.registration.atlas is export.atlas
        registration = export.slices[0].registration
        assert registration is not None
        assert registration.slice_coordinate_mm == -1.25
        assert registration.atlas_registration is not None
        assert registration.atlas_registration.landmarks[0].image.x == 10
        assert registration.detail_transform is not None
        assert len(registration.detail_transform.corners) == 4


def test_cli_json_inspects_full_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["inspect", str(full_export(tmp_path)), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["atlas"]["name"] == "Allen atlas"
    assert payload["modules"] == ["data", "registration", "classification"]
    assert payload["selectedClassifierHeadIdsByStaining"] == {
        "staining-1": "classifier-1"
    }


def test_classification_api(tmp_path: Path) -> None:
    with open_export(full_export(tmp_path)) as export:
        assert export.classification is not None
        classification = export.classification.for_staining("DAPI")
        assert classification.classifier.display_name == "DAPI classifier"
        assert classification.training_summary.training_run is not None
        assert classification.training_summary.training_run.status == "success"
        assert classification.find_training_samples(label="on", cell_id=2)
        assert not classification.find_training_samples(label="off")
        assert classification.find_omitted_slices(reason_code="no_source")
        info = classification.result_info(export.slices[0])
        assert isinstance(info.source, SharedDetectionSource)
        result = classification.load_result("slice-1")
        assert result.metadata is info
        assert result.cell_ids.tolist() == [1, 2]
        assert result.centroids.tolist() == [[10, 20], [30, 40]]
        assert result.positive_centroids.tolist() == [[30, 40]]
        assert (result.probabilities >= 0.75).tolist() == [False, True]
        results = classification.load_results()
        assert results.slice_ids.tolist() == ["slice-1", "slice-1"]
        assert results.positive_centroids.tolist() == [[30, 40]]
        assert results.by_slice["slice-1"] is not result
        with pytest.raises(TypeError):
            results.by_slice["other"] = result  # type: ignore[index]
        with pytest.raises(ObjectNotFoundError):
            classification.result_info("missing")
        with pytest.raises(ObjectNotFoundError):
            export.classification.for_staining("NeuN")


def test_match_api(tmp_path: Path) -> None:
    with open_export(full_export(tmp_path)) as export:
        assert export.classification is not None
        match = export.classification.match("dapi-neun")
        assert match.staining_a.name == "DAPI"
        assert match.staining_b.name == "NeuN"
        assert match.find_omitted_slices(slice="slice-1")
        assert match.result_index[0].side_b.detection_run_id == "run-2"
        result = match.load_result(export.slices[0])
        assert result.cell_ids_a.tolist() == [2]
        assert result.centroids_b.tolist() == [[31, 41]]
        assert result.algorithm_version == "v1"
        results = match.load_results()
        assert results.iou.tolist() == pytest.approx([0.417])
        assert results.by_slice["slice-1"].metadata is result.metadata
        with pytest.raises(ObjectNotFoundError):
            match.result_info("missing")
        with pytest.raises(ObjectNotFoundError):
            export.classification.match("missing")


def test_optional_modules_are_none() -> None:
    with open_export(MINIMAL) as export:
        assert export.atlas is None
        assert export.registration is None
        assert export.classification is None
        assert export.slices[0].cell_mask is None
        assert export.slices[0].registration is None


def test_bound_objects_reject_access_after_close(tmp_path: Path) -> None:
    export = open_export(full_export(tmp_path))
    animal = export.animals[0]
    export.close()
    with pytest.raises(ClosedExportError):
        _ = animal.name


def test_empty_aggregates(tmp_path: Path) -> None:
    root = full_export(tmp_path)
    index_path = root / "classification/stainings/staining-1/results/index.json"
    index = json.loads(index_path.read_text())
    index["slices"] = []
    write_json(index_path, index)
    match_path = root / "classification/matches/dapi-neun/match.json"
    match = json.loads(match_path.read_text())
    match["slices"] = []
    write_json(match_path, match)
    with open_export(root) as export:
        assert export.classification is not None
        assert (
            export.classification.for_staining("DAPI").load_results().cell_ids.size == 0
        )
        assert (
            export.classification.match("dapi-neun").load_results().cell_ids_a.size == 0
        )


def test_empty_match_result_may_omit_centroids(tmp_path: Path) -> None:
    root = full_export(tmp_path)
    match_path = root / "classification/matches/dapi-neun/match.json"
    match = json.loads(match_path.read_text())
    match["slices"][0]["matchedCount"] = 0
    write_json(match_path, match)
    result_path = root / "classification/matches/dapi-neun/slices/slice-1.npz"
    with np.load(result_path, allow_pickle=False) as archive:
        arrays = {
            name: archive[name]
            for name in archive.files
            if not name.startswith("centroids_")
        }
    for name, value in tuple(arrays.items()):
        if value.ndim == 1:
            arrays[name] = value[:0]
    np.savez(result_path, **arrays)
    with open_export(root) as export:
        assert export.classification is not None
        result = export.classification.match("dapi-neun").load_result("slice-1")
        assert result.centroids_a.shape == (0, 2)


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"cell_ids": np.array([1, 2], dtype=np.int64)}, "invalid_array"),
        ({"centroids_x": np.array([1], dtype=np.float32)}, "array_length"),
        ({"is_on": np.array([0, 2], dtype=np.uint8)}, "invalid_array"),
        ({"is_on": np.array([1, 0], dtype=np.uint8)}, "threshold_mismatch"),
        ({"threshold": np.array([0.7], dtype=np.float32)}, "threshold_mismatch"),
    ],
)
def test_invalid_classification_arrays(
    tmp_path: Path, changes: dict[str, np.ndarray[tuple[int, ...], np.dtype]], code: str
) -> None:
    root = full_export(tmp_path)
    result_path = (
        root / "classification/stainings/staining-1/results/slices/slice-1.npz"
    )
    with np.load(result_path, allow_pickle=True) as archive:
        arrays = {name: archive[name] for name in archive.files}
    arrays.update(changes)
    np.savez(result_path, **arrays)
    with open_export(root) as export:
        assert export.classification is not None
        with pytest.raises(InvalidExportError) as caught:
            export.classification.for_staining("DAPI").load_result("slice-1")
        assert caught.value.report.issues[0].code == code


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("schema_version", np.array(2, dtype=np.int32), "invalid_array"),
        ("algorithm_version", np.array(1, dtype=np.int32), "invalid_array"),
        ("overlap_threshold", np.array(1, dtype=np.int32), "invalid_array"),
        (
            "overlap_fraction_a",
            np.array([2], dtype=np.float32),
            "invalid_fraction",
        ),
        (
            "overlap_fraction_min",
            np.array([0.1], dtype=np.float32),
            "threshold_mismatch",
        ),
        ("algorithm_version", np.array("v2"), "index_mismatch"),
    ],
)
def test_invalid_match_arrays(
    tmp_path: Path, field: str, value: np.ndarray, code: str
) -> None:
    root = full_export(tmp_path)
    result_path = root / "classification/matches/dapi-neun/slices/slice-1.npz"
    with np.load(result_path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    arrays[field] = value
    np.savez(result_path, **arrays)
    with open_export(root) as export:
        assert export.classification is not None
        with pytest.raises(InvalidExportError) as caught:
            export.classification.match("dapi-neun").load_result("slice-1")
        assert caught.value.report.issues[0].code == code


def test_metadata_validation_is_aggregate(tmp_path: Path) -> None:
    root = full_export(tmp_path)
    classifier_path = root / "classification/stainings/staining-1/classifier.json"
    classifier = json.loads(classifier_path.read_text())
    classifier["staining"]["id"] = "wrong"
    write_json(classifier_path, classifier)
    samples_path = root / "classification/stainings/staining-1/training/samples.jsonl"
    samples_path.write_text("{\n")
    registration_path = root / "registration/slices/slice-1/atlas-registration.json"
    registration = json.loads(registration_path.read_text())
    registration["slideId"] = "wrong"
    registration["pointsV2"] = "bad"
    write_json(registration_path, registration)
    report = validate_export(root)
    assert not report.valid
    assert {
        "inconsistent_reference",
        "invalid_json",
        "inconsistent_slice",
        "invalid_field",
    } <= {issue.code for issue in report.issues}


def test_ambiguous_helper_error(tmp_path: Path) -> None:
    root = full_export(tmp_path)
    animals_path = root / "project/animals.json"
    animals = json.loads(animals_path.read_text())
    animals.append({**animals[0], "_id": "animal-2"})
    write_json(animals_path, animals)
    with pytest.raises(InvalidExportError) as caught:
        open_export(root)
    assert "duplicate_name" in {issue.code for issue in caught.value.report.issues}
    assert issubclass(AmbiguousNameError, LookupError)
