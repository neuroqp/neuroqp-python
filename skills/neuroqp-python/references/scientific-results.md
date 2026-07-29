# Scientific results

Read this reference before writing analyses of classifications or cell matches.

## Discover results

Classification data is optional. Inspect available stainings and opaque match keys rather than guessing them:

```python
with open_export(PROJECT_FILE) as export:
    module = export.classification
    if module is None:
        raise RuntimeError("This export has no classification data.")

    for classification in module.classifications:
        print(classification.staining.name, classification.classifier.display_name)
    for match in module.matches:
        print(match.pair_key, match.staining_a.name, match.staining_b.name)
```

Use `module.for_staining(...)` with an exact staining name, staining ID, or `Staining`. Use `module.match(pair_key)` with a displayed pair key.

## Classification arrays

For every row `i`, `cell_ids[i]`, `centroids[i]`, `probabilities[i]`, and `is_positive[i]` describe the same detected cell:

| Array | Shape | Meaning |
| --- | --- | --- |
| `cell_ids` | `(N,)` | Labels in the declared source detection mask |
| `centroids` | `(N, 2)` | Cell centres as `(x, y)` image pixels |
| `probabilities` | `(N,)` | Classifier probability |
| `is_positive` | `(N,)` | Exported positive/negative decision |

Use `is_positive` for the authoritative exported classification. It is validated against `probabilities >= threshold`. Apply another threshold only for an explicitly described sensitivity analysis.

Centroids use the source detection image or mask coordinate system. The origin is at the top-left, x increases rightward, and y increases downward. They are not micrometres or atlas coordinates. Use `(slice_id, cell_id)` as the unique cell key.

```python
with open_export(PROJECT_FILE) as export:
    module = export.classification
    if module is None:
        raise RuntimeError("This export has no classification data.")

    classification = module.for_staining("NeuN")
    results = classification.load_results()
    positive = results.is_positive
    positive_centroids = results.centroids[positive]
    positive_slice_ids = results.slice_ids[positive]
```

Keep all aligned arrays under the same mask. Slice-specific thresholds and metadata remain in `results.by_slice`.

## Omitted slices

An omitted slice has no result because the exporter recorded a reason. It is not a measured zero. Include `classification.omitted_slices` or `match.omitted_slices` in quality-control output and analysis tables.

## Match arrays

Each match row is a one-to-one cell pair. Always read `result.metadata.side_a` and `result.metadata.side_b`; pair-key spelling does not define NPZ side order.

| Value | Meaning |
| --- | --- |
| `intersection_area` | Pixels shared by both masks |
| `area_a`, `area_b` | Pixel area of each mask |
| `overlap_fraction_a`, `overlap_fraction_b` | Intersection divided by the corresponding area |
| `overlap_fraction_min` | Smaller side-specific overlap |
| `iou` | Intersection divided by union |

All fractions are between 0 and 1. Retained pairs satisfy `overlap_fraction_min >= overlap_threshold`. A zero matched count means no pairs passed; an omitted slice means no result was produced.

## Aggregate at the experimental unit

Build one row per analyzed slice with animal ID, group, condition, slice ID, AP coordinate, counts, and omission state. Aggregate slice counts to animal-level totals or means before comparing experimental groups when the animal is the experimental unit.

Do not use individual cells or slices as independent replicates unless the study design explicitly defines them that way. Carry detected-cell denominators when reporting positive fractions, and retain missing/omitted results separately from zeros.
