# Project objects

`open_export()` creates these reader-bound objects. Use their lookup and navigation methods rather than constructing them directly.

## ProjectExport

An open, validated NeuroQP project export.

### member

```
member(path: str) -> FileArtifact
```

Get a raw archive member as a file artifact.

### find_stainings

```
find_stainings(
    name: str | None = None,
) -> tuple[Staining, ...]
```

Find canonical staining names using a case/punctuation-insensitive alias.

## Animal

An animal and its slices.

## Slice

A project slice with navigation to related objects.

### image

```
image(image_id: str) -> Image
```

Get this slice's uniquely identified image.

### find_images

```
find_images(
    *,
    staining: Staining | Staining | str | None = None,
    magnification: str | None = None,
    filename: str | None = None,
) -> tuple[Image, ...]
```

Find images using any combination of common metadata fields.

## Image

An exported image artifact.

### size_bytes

```
size_bytes: int
```

Encoded image-file size in bytes.

### open

```
open() -> BinaryIO
```

Open the exact archived image member.

### as_path

```
as_path(
    *, directory: str | Path | None = None
) -> AbstractContextManager[Path]
```

Provide the image as a filesystem path within a context manager.

## Staining

A project staining.

## FileArtifact

A file contained in an open export.

### size_bytes

```
size_bytes: int
```

Encoded artifact size in bytes.

This is the stored file size, not the memory required for decoded image pixels.

### open

```
open() -> BinaryIO
```

Open the artifact as a binary stream.

Returns:

| Type       | Description                                                             |
| ---------- | ----------------------------------------------------------------------- |
| `BinaryIO` | A native file stream for an extracted export or a streaming ZIP member. |

Notes

Close the stream before closing its parent export.

### as_path

```
as_path(
    *, directory: str | Path | None = None
) -> Iterator[Path]
```

Provide a filesystem path for the artifact.

Parameters:

| Name        | Type  | Description | Default |
| ----------- | ----- | ----------- | ------- |
| `directory` | \`str | Path        | None\`  |

Returns:

| Type                           | Description                                                                                               |
| ------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `AbstractContextManager[Path]` | A context manager yielding the original path for a directory export or a temporary copy for a ZIP export. |

Notes

Use the path only inside this context and while the parent export is open. Temporary ZIP copies are removed when the context exits.

## Registration

Registration module access.

### for_slice

```
for_slice(
    slice_: Slice | Slice | str,
) -> SliceRegistration | None
```

Return available registration data for one slice.

## SliceRegistration

Available registration data for one slice.

## ClassificationModule

Provide the classifications and cell matches included in an export.

Attributes:

| Name              | Type | Description                                          |
| ----------------- | ---- | ---------------------------------------------------- |
| `classifications` |      | Selected classifications, one per included staining. |
| `matches`         |      | Included staining-pair cell matches.                 |

### for_staining

```
for_staining(
    staining: Staining | Staining | str,
) -> Classification
```

Get the selected classification for a staining.

Parameters:

| Name       | Type       | Description | Default |
| ---------- | ---------- | ----------- | ------- |
| `staining` | \`Staining | Staining    | str\`   |

Returns:

| Type             | Description                                |
| ---------------- | ------------------------------------------ |
| `Classification` | Selected classifier and available results. |

Raises:

| Type                  | Description                                           |
| --------------------- | ----------------------------------------------------- |
| `ObjectNotFoundError` | If the export has no classification for the staining. |
| `AmbiguousNameError`  | If the staining name is not unique.                   |

### match

```
match(pair_key: str) -> Match
```

Get a staining-pair match by its exported key.

Parameters:

| Name       | Type  | Description                        | Default    |
| ---------- | ----- | ---------------------------------- | ---------- |
| `pair_key` | `str` | Key discovered from :attr:matches. | *required* |

Returns:

| Type    | Description                                 |
| ------- | ------------------------------------------- |
| `Match` | Match metadata and available slice results. |

Raises:

| Type                  | Description                     |
| --------------------- | ------------------------------- |
| `ObjectNotFoundError` | If the pair key is not present. |

## Classification

Provide classifier metadata and results for one staining.

Attributes:

| Name               | Type | Description                                             |
| ------------------ | ---- | ------------------------------------------------------- |
| `staining`         |      | Classified project staining.                            |
| `classifier`       |      | Selected classifier metadata.                           |
| `training_summary` |      | Training summary current at export time.                |
| `training_samples` |      | Exported positive and negative training samples.        |
| `result_index`     |      | Slice-level result metadata available for lazy loading. |
| `omitted_slices`   |      | Documented slices without a result.                     |

### find_training_samples

```
find_training_samples(
    *,
    slice: Slice | Slice | str | None = None,
    label: str | None = None,
    cell_id: int | None = None,
) -> tuple[TrainingSample, ...]
```

Filter exported training samples.

Parameters:

| Name      | Type    | Description | Default                                 |
| --------- | ------- | ----------- | --------------------------------------- |
| `slice`   | \`Slice | Slice       | str                                     |
| `label`   | \`str   | None\`      | Exported label, normally "on" or "off". |
| `cell_id` | \`int   | None\`      | Cell label to include.                  |

Returns:

| Type                      | Description                             |
| ------------------------- | --------------------------------------- |
| `tuple of TrainingSample` | Samples matching every supplied filter. |

### find_omitted_slices

```
find_omitted_slices(
    *,
    slice: Slice | Slice | str | None = None,
    reason_code: str | None = None,
) -> tuple[SliceExclusion, ...]
```

Filter slices that have no classification result.

Parameters:

| Name          | Type    | Description | Default                                 |
| ------------- | ------- | ----------- | --------------------------------------- |
| `slice`       | \`Slice | Slice       | str                                     |
| `reason_code` | \`str   | None\`      | Stable exporter reason code to include. |

Returns:

| Type                      | Description                               |
| ------------------------- | ----------------------------------------- |
| `tuple of SliceExclusion` | Omissions matching every supplied filter. |

### result_info

```
result_info(
    slice_: Slice | Slice | str,
) -> ClassificationResultInfo
```

Get result metadata for one slice without loading arrays.

Parameters:

| Name     | Type    | Description | Default |
| -------- | ------- | ----------- | ------- |
| `slice_` | \`Slice | Slice       | str\`   |

Returns:

| Type                       | Description                  |
| -------------------------- | ---------------------------- |
| `ClassificationResultInfo` | Slice-level result metadata. |

Raises:

| Type                  | Description                                |
| --------------------- | ------------------------------------------ |
| `ObjectNotFoundError` | If the slice has no classification result. |

### load_result

```
load_result(
    slice_: Slice | Slice | str,
) -> ClassificationResult
```

Load and validate one slice's classification arrays.

Parameters:

| Name     | Type    | Description | Default |
| -------- | ------- | ----------- | ------- |
| `slice_` | \`Slice | Slice       | str\`   |

Returns:

| Type                   | Description                                                      |
| ---------------------- | ---------------------------------------------------------------- |
| `ClassificationResult` | Aligned cell IDs, centroids, probabilities, and classifications. |

Raises:

| Type                  | Description                                |
| --------------------- | ------------------------------------------ |
| `ObjectNotFoundError` | If the slice has no classification result. |
| `InvalidExportError`  | If the stored arrays fail validation.      |
| `ClosedExportError`   | If the parent export is closed.            |

### load_results

```
load_results() -> ClassificationResults
```

Load and concatenate every available slice result.

Returns:

| Type                    | Description                                             |
| ----------------------- | ------------------------------------------------------- |
| `ClassificationResults` | Aligned arrays with a slice ID for every detected cell. |

Raises:

| Type                 | Description                            |
| -------------------- | -------------------------------------- |
| `InvalidExportError` | If any stored result fails validation. |
| `ClosedExportError`  | If the parent export is closed.        |

## Match

Provide cell-match metadata and results for one staining pair.

Attributes:

| Name                     | Type | Description                                                                                                 |
| ------------------------ | ---- | ----------------------------------------------------------------------------------------------------------- |
| `pair_key`               |      | Opaque exported key used to retrieve this match.                                                            |
| `staining_a, staining_b` |      | Stainings in the exported pair definition. Read each result's metadata for its actual NPZ side orientation. |
| `result_index`           |      | Slice-level match metadata available for lazy loading.                                                      |
| `omitted_slices`         |      | Documented slices without a match result.                                                                   |

### find_omitted_slices

```
find_omitted_slices(
    *,
    slice: Slice | Slice | str | None = None,
    reason_code: str | None = None,
) -> tuple[SliceExclusion, ...]
```

Filter slices that have no match result.

Parameters:

| Name          | Type    | Description | Default                                 |
| ------------- | ------- | ----------- | --------------------------------------- |
| `slice`       | \`Slice | Slice       | str                                     |
| `reason_code` | \`str   | None\`      | Stable exporter reason code to include. |

Returns:

| Type                      | Description                               |
| ------------------------- | ----------------------------------------- |
| `tuple of SliceExclusion` | Omissions matching every supplied filter. |

### result_info

```
result_info(slice_: Slice | Slice | str) -> MatchResultInfo
```

Get match metadata for one slice without loading arrays.

Parameters:

| Name     | Type    | Description | Default |
| -------- | ------- | ----------- | ------- |
| `slice_` | \`Slice | Slice       | str\`   |

Returns:

| Type              | Description                                            |
| ----------------- | ------------------------------------------------------ |
| `MatchResultInfo` | Slice-level match metadata, including side identities. |

Raises:

| Type                  | Description                       |
| --------------------- | --------------------------------- |
| `ObjectNotFoundError` | If the slice has no match result. |

### load_result

```
load_result(slice_: Slice | Slice | str) -> MatchResult
```

Load and validate one slice's match arrays.

Parameters:

| Name     | Type    | Description | Default |
| -------- | ------- | ----------- | ------- |
| `slice_` | \`Slice | Slice       | str\`   |

Returns:

| Type          | Description                          |
| ------------- | ------------------------------------ |
| `MatchResult` | Aligned one-to-one cell-pair arrays. |

Raises:

| Type                  | Description                           |
| --------------------- | ------------------------------------- |
| `ObjectNotFoundError` | If the slice has no match result.     |
| `InvalidExportError`  | If the stored arrays fail validation. |
| `ClosedExportError`   | If the parent export is closed.       |

### load_results

```
load_results() -> MatchResults
```

Load and concatenate every available slice match.

Returns:

| Type           | Description                                            |
| -------------- | ------------------------------------------------------ |
| `MatchResults` | Aligned arrays with a slice ID for every matched pair. |

Raises:

| Type                 | Description                           |
| -------------------- | ------------------------------------- |
| `InvalidExportError` | If any stored match fails validation. |
| `ClosedExportError`  | If the parent export is closed.       |
