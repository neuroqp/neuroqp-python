# Scientific results

Classification and match loaders return these containers. Their arrays align by row and are documented with shapes, dtypes, units, and side semantics below.

## ClassificationResult

Store aligned classification arrays for one slice.

Attributes:

| Name            | Type                       | Description                                                                                                                                                 |
| --------------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `metadata`      | `ClassificationResultInfo` | Slice, staining, classifier, lineage, and timestamp metadata.                                                                                               |
| `cell_ids`      | `Array`                    | (N,) int32 labels from the source detection mask.                                                                                                           |
| `centroids`     | `Array`                    | (N, 2) float32 pixel coordinates in (x, y) order. The origin is the top-left of the source detection image or mask; x increases right and y increases down. |
| `probabilities` | `Array`                    | (N,) float32 classifier probabilities.                                                                                                                      |
| `is_positive`   | `Array`                    | (N,) boolean mask. It is the authoritative exported classification and equals probabilities >= threshold.                                                   |
| `threshold`     | `float`                    | Probability threshold used for this slice.                                                                                                                  |

Notes

Every row index refers to the same detected cell across all arrays. Coordinates are image pixels, not micrometres or atlas coordinates.

### positive_centroids

```
positive_centroids: Array
```

Return `centroids` rows classified as positive.

## ClassificationResults

Store aligned classification arrays concatenated across slices.

Attributes:

| Name            | Type                                          | Description                                                         |
| --------------- | --------------------------------------------- | ------------------------------------------------------------------- |
| `cell_ids`      | `Array`                                       | (N,) int32 cell labels. Labels are unique only within a slice.      |
| `slice_ids`     | `Array`                                       | (N,) slice identifiers aligned with every other array.              |
| `centroids`     | `Array`                                       | (N, 2) float32 source-image pixel coordinates in (x, y) order.      |
| `probabilities` | `Array`                                       | (N,) float32 classifier probabilities.                              |
| `is_positive`   | `Array`                                       | (N,) authoritative boolean classification mask.                     |
| `by_slice`      | `MappingProxyType[str, ClassificationResult]` | Read-only mapping from slice ID to its :class:ClassificationResult. |

Notes

Use `(slice_id, cell_id)` as a cell key. Thresholds can differ by slice and remain available through :attr:`by_slice`.

### positive_centroids

```
positive_centroids: Array
```

Return `centroids` rows classified as positive.

## MatchResult

Store aligned one-to-one cell matches for one slice.

Attributes:

| Name                                     | Type              | Description                                                                              |
| ---------------------------------------- | ----------------- | ---------------------------------------------------------------------------------------- |
| `metadata`                               | `MatchResultInfo` | Slice metadata and the actual staining and detection run assigned to each side.          |
| `cell_ids_a, cell_ids_b`                 |                   | (M,) int32 cell labels for sides A and B.                                                |
| `centroids_a, centroids_b`               |                   | (M, 2) float32 source-mask pixel coordinates in (x, y) order for the corresponding side. |
| `intersection_area`                      | `Array`           | (M,) int32 overlap area in pixels.                                                       |
| `area_a, area_b`                         |                   | (M,) int32 cell-mask areas in pixels for each side.                                      |
| `overlap_fraction_a, overlap_fraction_b` |                   | Intersection area divided by the corresponding side's area.                              |
| `overlap_fraction_min`                   | `Array`           | Smaller of the two side-specific overlap fractions.                                      |
| `iou`                                    | `Array`           | Intersection over union: intersection / (area_a + area_b - intersection).                |
| `algorithm_version`                      | `str`             | Matching algorithm version.                                                              |
| `overlap_threshold`                      | `float`           | Minimum overlap_fraction_min retained by the matching algorithm.                         |

Notes

Every row index describes one matched pair. Read side identities from `metadata.side_a` and `metadata.side_b`; do not infer them from the pair key.

## MatchResults

Store aligned cell-match arrays concatenated across slices.

Attributes:

| Name                                     | Type                                 | Description                                                                      |
| ---------------------------------------- | ------------------------------------ | -------------------------------------------------------------------------------- |
| `slice_ids`                              | `Array`                              | (M,) slice identifiers aligned with every other array.                           |
| `cell_ids_a, cell_ids_b`                 |                                      | (M,) int32 cell labels for sides A and B. Labels are unique only within a slice. |
| `centroids_a, centroids_b`               |                                      | (M, 2) float32 source-mask pixel coordinates in (x, y) order.                    |
| `intersection_area, area_a, area_b`      |                                      | (M,) pixel-area arrays.                                                          |
| `overlap_fraction_a, overlap_fraction_b` |                                      | (M,) side-specific intersection fractions.                                       |
| `overlap_fraction_min`                   | `Array`                              | (M,) smaller side-specific overlap fraction.                                     |
| `iou`                                    | `Array`                              | (M,) intersection-over-union values.                                             |
| `by_slice`                               | `MappingProxyType[str, MatchResult]` | Read-only mapping from slice ID to its :class:MatchResult.                       |

Notes

Use `(slice_id, cell_id)` to identify cells. Side identities and thresholds remain available through :attr:`by_slice`.
