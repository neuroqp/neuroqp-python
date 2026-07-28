"""Synthetic full v2 export builder for tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

FIXTURES = Path(__file__).parent / "fixtures"
MINIMAL = FIXTURES / "minimal-v2"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def full_export(tmp_path: Path) -> Path:
    root = tmp_path / "full"
    shutil.copytree(MINIMAL, root)

    manifest = json.loads((root / "manifest.json").read_text())
    manifest.update(
        {
            "includedModules": ["data", "registration", "classification"],
            "atlas": {
                "id": "atlas-1",
                "key": "allen",
                "version": "v1",
                "name": "Allen atlas",
            },
            "selectedClassifierHeadIdsByStaining": {"staining-1": "classifier-1"},
            "linkedTrainingRunIdsByStaining": {"staining-1": "training-1"},
        }
    )
    write_json(root / "manifest.json", manifest)
    metadata = json.loads((root / "project/export.json").read_text())
    metadata["requestedModules"] = ["data", "registration", "classification"]
    metadata["selectedClassifierHeadIdsByStaining"] = {"staining-1": "classifier-1"}
    write_json(root / "project/export.json", metadata)
    project = json.loads((root / "project/project.json").read_text())
    project["atlasId"] = "atlas-1"
    write_json(root / "project/project.json", project)
    write_json(
        root / "project/stainings.json",
        [
            {"_id": "staining-1", "name": "DAPI"},
            {"_id": "staining-2", "name": "NeuN"},
        ],
    )
    (root / "data/slices/slice-1/detection").mkdir()
    (root / "data/slices/slice-1/detection/cell-mask.tif").write_bytes(b"mask")

    write_json(
        root / "registration/atlas/atlas-manifest.json",
        {
            "id": "atlas-1",
            "key": "allen",
            "version": "v1",
            "name": "Allen atlas",
            "species": "mouse",
            "plane": "coronal",
            "spec": {"rasterWidthPx": 456},
        },
    )
    write_json(
        root / "registration/slices/slice-1/atlas-registration.json",
        {
            "slideId": "slice-1",
            "apMm": -1.25,
            "pointsV2": [
                {
                    "imageXPx": 10,
                    "imageYPx": 20,
                    "atlasPlaneXMm": 1.5,
                    "atlasPlaneYMm": 2.5,
                }
            ],
        },
    )
    write_json(
        root / "registration/slices/slice-1/detail-to-whole-slice.json",
        {
            "slideId": "slice-1",
            "corners": [
                {"x": 0, "y": 0},
                {"x": 1, "y": 0},
                {"x": 1, "y": 1},
                {"x": 0, "y": 1},
            ],
        },
    )

    classifier_path = "classification/stainings/staining-1/classifier.json"
    summary_path = "classification/stainings/staining-1/training/summary.json"
    samples_path = "classification/stainings/staining-1/training/samples.jsonl"
    index_path = "classification/stainings/staining-1/results/index.json"
    result_path = "classification/stainings/staining-1/results/slices/slice-1.npz"
    match_path = "classification/matches/dapi-neun/match.json"
    match_result_path = "classification/matches/dapi-neun/slices/slice-1.npz"
    staining_1 = {"id": "staining-1", "name": "DAPI"}
    staining_2 = {"id": "staining-2", "name": "NeuN"}
    exclusion = {
        "sliceId": "slice-1",
        "sliceName": "Slice 1",
        "reasonCode": "no_source",
        "reason": "No source result",
    }
    write_json(
        root / "classification/manifest.json",
        {
            "exportVersion": "v2",
            "stainings": [
                {
                    "staining": staining_1,
                    "classifier": {
                        "id": "classifier-1",
                        "displayName": "DAPI classifier",
                    },
                    "classifierPath": classifier_path,
                    "trainingSummaryPath": summary_path,
                    "trainingSamplesPath": samples_path,
                    "resultIndexPath": index_path,
                    "exclusions": [exclusion],
                }
            ],
            "matches": [
                {
                    "pairKey": "dapi-neun",
                    "stainingA": staining_1,
                    "stainingB": staining_2,
                    "matchPath": match_path,
                    "exclusions": [],
                }
            ],
        },
    )
    write_json(
        root / classifier_path,
        {
            "id": "classifier-1",
            "displayName": "DAPI classifier",
            "version": 1,
            "headType": "staining_specific",
            "source": "trained",
            "createdAt": 1785240000000,
            "comments": None,
            "staining": staining_1,
            "trainingRunId": "training-1",
            "evaluationMetrics": {"accuracy": 1},
        },
    )
    write_json(
        root / summary_path,
        {
            "staining": staining_1,
            "sampleBasis": "current_at_export",
            "currentSamples": {"on": 1, "off": 0, "total": 1, "sliceCount": 1},
            "trainingRun": {
                "id": "training-1",
                "status": "success",
                "trainingDurationMs": 100,
                "finalMetrics": {"accuracy": 1},
                "recordedSampleCounts": {"on": 1, "off": 0, "total": 1},
                "histories": {"trainLoss": [0.1]},
            },
        },
    )
    samples_file = root / samples_path
    samples_file.parent.mkdir(parents=True, exist_ok=True)
    samples_file.write_text(
        json.dumps(
            {
                "sliceId": "slice-1",
                "sliceName": "Slice 1",
                "stainingId": "staining-1",
                "stainingName": "DAPI",
                "cellId": 2,
                "label": "on",
                "createdAt": 1785240000000,
            }
        )
        + "\n"
    )
    classification_info = {
        "sliceId": "slice-1",
        "sliceName": "Slice 1",
        "stainingId": "staining-1",
        "classifierId": "classifier-1",
        "sourceLineage": {
            "kind": "shared_detection",
            "cellCountId": "count-1",
        },
        "onCount": 1,
        "offCount": 1,
        "threshold": 0.5,
        "timestamp": 1785240000000,
        "npzPath": result_path,
    }
    write_json(
        root / index_path,
        {
            "staining": staining_1,
            "classifier": {
                "id": "classifier-1",
                "name": "DAPI classifier",
            },
            "slices": [classification_info],
        },
    )
    result_file = root / result_path
    result_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        result_file,
        cell_ids=np.array([1, 2], dtype=np.int32),
        centroids_x=np.array([10, 30], dtype=np.float32),
        centroids_y=np.array([20, 40], dtype=np.float32),
        intensities=np.array([0.2, 0.8], dtype=np.float32),
        is_on=np.array([0, 1], dtype=np.uint8),
        threshold=np.array([0.5], dtype=np.float32),
        staining=np.array(["DAPI"], dtype=object),
    )

    match_info = {
        "sliceId": "slice-1",
        "sliceName": "Slice 1",
        "sideA": {
            "staining": staining_1,
            "detectionRunId": "run-1",
            "unmatchedCount": 1,
        },
        "sideB": {
            "staining": staining_2,
            "detectionRunId": "run-2",
            "unmatchedCount": 0,
        },
        "algorithmVersion": "v1",
        "overlapThreshold": 0.5,
        "timestamp": 1785240000000,
        "candidatePairCount": 2,
        "matchedCount": 1,
        "npzPath": match_result_path,
    }
    write_json(
        root / match_path,
        {
            "pairKey": "dapi-neun",
            "stainingA": staining_1,
            "stainingB": staining_2,
            "exclusions": [exclusion],
            "slices": [match_info],
        },
    )
    match_file = root / match_result_path
    match_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        match_file,
        schema_version=np.array(1, dtype=np.int32),
        algorithm_version=np.array("v1"),
        overlap_threshold=np.array(0.5, dtype=np.float32),
        cell_ids_a=np.array([2], dtype=np.int32),
        cell_ids_b=np.array([8], dtype=np.int32),
        centroids_x_a=np.array([30], dtype=np.float32),
        centroids_y_a=np.array([40], dtype=np.float32),
        centroids_x_b=np.array([31], dtype=np.float32),
        centroids_y_b=np.array([41], dtype=np.float32),
        intersection_area=np.array([5], dtype=np.int32),
        area_a=np.array([8], dtype=np.int32),
        area_b=np.array([9], dtype=np.int32),
        overlap_fraction_a=np.array([0.625], dtype=np.float32),
        overlap_fraction_b=np.array([0.556], dtype=np.float32),
        overlap_fraction_min=np.array([0.556], dtype=np.float32),
        iou=np.array([0.417], dtype=np.float32),
    )
    return root
