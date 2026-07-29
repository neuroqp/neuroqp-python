# Classification and cell matches

Classification data is available only when the export includes the classification module. All result arrays are loaded on demand and remain usable after the export closes.

## Discover available results

Do not guess staining names or match keys. Inspect what the export contains:

```
from neuroqp import open_export

with open_export("project.zip") as export:
    module = export.classification
    if module is None:
        raise RuntimeError("This export does not include classification data.")

    for classification in module.classifications:
        print(
            classification.staining.name,
            classification.classifier.display_name,
            len(classification.result_index),
        )

    for match in module.matches:
        print(match.pair_key, match.staining_a.name, match.staining_b.name)
```

Pass an exact staining name, staining ID, or `Staining` object to `for_staining()`. Pass one of the displayed `pair_key` values to `match()`.

## Load classification results

Load one slice when you need its result:

```
from neuroqp import open_export

with open_export("project.zip") as export:
    module = export.classification
    if module is None:
        raise RuntimeError("This export does not include classification data.")

    classification = module.for_staining("NeuN")
    slice_ = export.slices[0]
    result = classification.load_result(slice_)

    print(result)
    print(result.cell_ids)
    print(result.centroids)
    print(result.probabilities)
    print(result.is_positive)
```

The arrays align by row:

| Array           | Shape    | Meaning                                        |
| --------------- | -------- | ---------------------------------------------- |
| `cell_ids`      | `(N,)`   | Cell labels from the source detection mask     |
| `centroids`     | `(N, 2)` | Cell centres as `(x, y)` image pixels          |
| `probabilities` | `(N,)`   | Classifier probability for each cell           |
| `is_positive`   | `(N,)`   | Authoritative positive/negative classification |

For a row index `i`, all four arrays describe the same detected cell. `is_positive` is validated against `probabilities >= result.threshold`; use it when you want the classification exported by NeuroQP. Apply a different probability threshold only when your analysis intentionally reclassifies the cells.

Centroid coordinates use the source detection image or mask coordinate system. `(0, 0)` is the top-left, x increases to the right, and y increases downward. They are pixels, not micrometres or atlas coordinates. NeuroQP Python does not yet transform these centroids into atlas space.

Load and concatenate all available slices when vectorized analysis is more convenient:

```
from neuroqp import open_export

with open_export("project.zip") as export:
    module = export.classification
    if module is None:
        raise RuntimeError("This export does not include classification data.")

    results = module.for_staining("NeuN").load_results()
    positive_rows = results.is_positive

    positive_slice_ids = results.slice_ids[positive_rows]
    positive_cell_ids = results.cell_ids[positive_rows]
    positive_centroids = results.centroids[positive_rows]
```

`slice_ids`, `cell_ids`, `centroids`, `probabilities`, and `is_positive` remain aligned after concatenation. Cell IDs are labels in a slice-level detection mask and can repeat between slices, so use `(slice_id, cell_id)` as the unique cell key. Slice-specific thresholds and metadata remain available through `results.by_slice`.

## Training samples and omitted slices

Training samples are metadata and do not load result arrays:

```
from neuroqp import open_export

with open_export("project.zip") as export:
    module = export.classification
    if module is None:
        raise RuntimeError("This export does not include classification data.")

    classification = module.for_staining("NeuN")
    positive_samples = classification.find_training_samples(label="on")

    for omission in classification.omitted_slices:
        print(omission.slice_name, omission.reason_code, omission.reason)
```

An omitted slice is not a zero count. It has no result because the exporter recorded a specific reason, such as a missing or outdated source. Keep omissions visible when building analysis tables instead of silently replacing them with zeros.

## Load and interpret cell matches

Match keys are opaque export identifiers. Discover them from `module.matches`, then load the selected match:

```
from neuroqp import open_export

with open_export("project.zip") as export:
    module = export.classification
    if module is None or not module.matches:
        raise RuntimeError("This export does not include cell matches.")

    available = module.matches[0]
    match = module.match(available.pair_key)
    result = match.load_result(match.result_index[0].slice_id)

    print(result.metadata.side_a.staining.name)
    print(result.metadata.side_b.staining.name)
    print(result.cell_ids_a, result.cell_ids_b)
    print(result.iou)

    for omission in match.omitted_slices:
        print(omission.slice_name, omission.reason_code, omission.reason)
```

Each row describes one one-to-one matched pair. Side A arrays align with `result.metadata.side_a`; side B arrays align with `result.metadata.side_b`. Always read these metadata records because the NPZ side order can differ from the staining order suggested by a pair key.

The match measurements are:

| Value                  | Definition                                                  |
| ---------------------- | ----------------------------------------------------------- |
| `intersection_area`    | Pixels shared by both cell masks                            |
| `area_a`, `area_b`     | Pixel area of each cell mask                                |
| `overlap_fraction_a`   | `intersection_area / area_a`                                |
| `overlap_fraction_b`   | `intersection_area / area_b`                                |
| `overlap_fraction_min` | Smaller of the two overlap fractions                        |
| `iou`                  | `intersection_area / (area_a + area_b - intersection_area)` |

All fractions and IoU are between 0 and 1. Retained pairs satisfy `overlap_fraction_min >= overlap_threshold`, and each cell occurs at most once on its side. Match centroids use the source mask's `(x, y)` pixel coordinates. As with classifications, keep omitted matches separate from measured zero matches.

## Aggregate results by animal and experimental group

Pandas is optional but convenient for analysis tables:

```
python -m pip install pandas
```

Build one row per analyzed slice, then aggregate to the animal level before comparing groups:

```
import pandas as pd

from neuroqp import open_export

rows = []

with open_export("project.zip") as export:
    module = export.classification
    if module is None:
        raise RuntimeError("This export does not include classification data.")

    classification = module.for_staining("NeuN")

    for info in classification.result_index:
        slice_ = export.slice(info.slice_id)
        animal = slice_.animal
        result = classification.load_result(slice_)
        detected_cells = int(result.cell_ids.size)
        positive_cells = int(result.is_positive.sum())

        rows.append(
            {
                "animal_id": animal.id,
                "animal": animal.name,
                "group": animal.metadata.group,
                "condition": animal.metadata.condition,
                "slice_id": slice_.id,
                "slice": slice_.name,
                "ap_mm": slice_.slice_coordinate_mm,
                "positive_cells": positive_cells,
                "detected_cells": detected_cells,
            }
        )

if not rows:
    raise RuntimeError("This staining has no classification results.")

per_slice = pd.DataFrame(rows)

per_animal = (
    per_slice.groupby(
        ["animal_id", "animal", "group", "condition"],
        dropna=False,
        as_index=False,
    )
    .agg(
        slices=("slice_id", "nunique"),
        positive_cells=("positive_cells", "sum"),
        detected_cells=("detected_cells", "sum"),
    )
)
per_animal["positive_fraction"] = (
    per_animal["positive_cells"]
    / per_animal["detected_cells"].replace(0, pd.NA)
)

group_summary = (
    per_animal.groupby(["group", "condition"], dropna=False, as_index=False)
    .agg(
        n_animals=("animal_id", "nunique"),
        mean_positive_cells=("positive_cells", "mean"),
        sem_positive_cells=("positive_cells", "sem"),
        mean_positive_fraction=("positive_fraction", "mean"),
    )
)

print(group_summary)
```

Choose the aggregation that matches the experimental design. If the animal is the experimental unit, do not treat individual cells or slices as independent replicates. Keep `classification.omitted_slices` beside the result table so missing analyses remain distinguishable from measured zero counts.

The SDK validates required array names, dtypes, shapes, lengths, fraction ranges, masks, thresholds, declared counts, and one-to-one match constraints when results load. NumPy archives are always opened with `allow_pickle=False`.
