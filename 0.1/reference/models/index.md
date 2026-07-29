# Metadata models

These immutable records are returned by project objects and result loaders. Analysis code normally reads their attributes rather than constructing them directly. Python field names use `snake_case`; the [export specification](https://python.neuroqp.com/0.1/specifications/export-v2/index.md) documents the original JSON field names.

## Project and registration

## Manifest

Describe the identity and included content of a v2 export.

Attributes:

| Name                                       | Type                 | Description                                                  |
| ------------------------------------------ | -------------------- | ------------------------------------------------------------ |
| `export_version`                           | `Literal['v2']`      | Export format version. It is "v2" for this model.            |
| `export_id`                                | `str`                | Opaque identifier for this export snapshot.                  |
| `exported_at`                              | `NormalizedDatetime` | Snapshot creation time as a timezone-aware UTC datetime.     |
| `project`                                  | `ManifestProject`    | Project identifier, slug, and name recorded by the exporter. |
| `project_metadata_path`                    | `str`                | Archive path to the export metadata record.                  |
| `included_modules`                         | `tuple[Module, ...]` | Modules actually included in the export.                     |
| `atlas`                                    | \`AtlasSummary       | None\`                                                       |
| `selected_classifier_head_ids_by_staining` | `dict[str, str]`     | Mapping from staining IDs to selected classifier IDs.        |
| `linked_training_run_ids_by_staining`      | \`dict\[str, str     | None\]\`                                                     |

## ExportMetadata

Describe how and when an export snapshot was requested.

Attributes:

| Name                                       | Type                 | Description                                              |
| ------------------------------------------ | -------------------- | -------------------------------------------------------- |
| `export_version`                           | `Literal['v2']`      | Export format version.                                   |
| `exported_at`                              | `NormalizedDatetime` | Snapshot creation time as a timezone-aware UTC datetime. |
| `export_id`                                | `str`                | Opaque identifier matching :attr:Manifest.export_id.     |
| `project_id`                               | `str`                | Opaque project identifier.                               |
| `expires_at`                               | `NormalizedDatetime` | Expiry time of the source export request.                |
| `requested_modules`                        | `tuple[Module, ...]` | Modules requested when the export was created.           |
| `selected_classifier_head_ids_by_staining` | `dict[str, str]`     | Mapping from staining IDs to selected classifier IDs.    |

## ProjectMetadata

Describe the project's image scales and annotations.

Attributes:

| Name                            | Type    | Description                                            |
| ------------------------------- | ------- | ------------------------------------------------------ |
| `name`                          | `str`   | Human-readable project name.                           |
| `type`                          | `str`   | Project imaging type recorded by NeuroQP.              |
| `atlas_id`                      | \`str   | None\`                                                 |
| `whole_slice_label`             | `str`   | Display label for whole-slice images.                  |
| `whole_slice_microns_per_pixel` | `float` | Whole-slice image pixel size in micrometres per pixel. |
| `detail_image_label`            | `str`   | Display label for detail images.                       |
| `detail_microns_per_pixel`      | `float` | Detail-image pixel size in micrometres per pixel.      |
| `comments`                      | \`str   | None\`                                                 |

## Atlas

Describe the atlas selected for the exported project.

Attributes:

| Name            | Type             | Description                                       |
| --------------- | ---------------- | ------------------------------------------------- |
| `id`            | `str`            | Opaque atlas identifier.                          |
| `key`           | `str`            | Stable atlas family key.                          |
| `version`       | `str`            | Atlas data version.                               |
| `name`          | `str`            | Human-readable atlas name.                        |
| `species`       | `str`            | Species described by the atlas.                   |
| `plane`         | `str`            | Sectioning plane, such as "coronal".              |
| `specification` | `dict[str, Any]` | Additive atlas specification supplied by NeuroQP. |

## AtlasRegistration

Describe the atlas landmarks for one slice.

Attributes:

| Name                  | Type                               | Description                                              |
| --------------------- | ---------------------------------- | -------------------------------------------------------- |
| `slice_id`            | `str`                              | Identifier of the registered slice.                      |
| `slice_coordinate_mm` | `float`                            | Registered anterior-posterior coordinate in millimetres. |
| `landmarks`           | `tuple[RegistrationLandmark, ...]` | Corresponding image-pixel and atlas-plane points.        |

## BrainRegion

Identify an atlas brain region selected in the project.

Attributes:

| Name           | Type  | Description                                         |
| -------------- | ----- | --------------------------------------------------- |
| `structure_id` | `int` | Numeric structure identifier assigned by the atlas. |
| `name`         | `str` | Full region name.                                   |
| `acronym`      | `str` | Atlas region acronym.                               |

## DetailTransform

Describe a detail image's footprint in whole-slice pixel coordinates.

Attributes:

| Name       | Type                | Description                                                          |
| ---------- | ------------------- | -------------------------------------------------------------------- |
| `slice_id` | `str`               | Identifier of the transformed slice.                                 |
| `corners`  | `tuple[Point, ...]` | Ordered detail-image corners expressed as whole-slice (x, y) pixels. |

## Classification and matching

## ClassifierMetadata

Describe the classifier selected for one staining.

Attributes:

| Name                 | Type                                                      | Description                                                     |
| -------------------- | --------------------------------------------------------- | --------------------------------------------------------------- |
| `id`                 | `str`                                                     | Opaque classifier-head identifier.                              |
| `display_name`       | `str`                                                     | Human-readable classifier name.                                 |
| `version`            | `int`                                                     | Numeric classifier version.                                     |
| `head_type`          | `str`                                                     | Classifier-head type recorded by NeuroQP.                       |
| `source`             | `Literal['trained', 'platform_import', 'project_import']` | Whether the classifier was trained in this project or imported. |
| `created_at`         | `NormalizedDatetime`                                      | Creation time as a timezone-aware UTC datetime.                 |
| `comments`           | \`str                                                     | None\`                                                          |
| `staining`           | `EntityReference`                                         | Staining identity associated with the classifier.               |
| `training_run_id`    | \`str                                                     | None\`                                                          |
| `evaluation_metrics` | `dict[str, Any]`                                          | Additive evaluation metrics recorded for the classifier.        |

## TrainingSummary

Summarize classifier training data for one staining.

Attributes:

| Name              | Type                           | Description                                                            |
| ----------------- | ------------------------------ | ---------------------------------------------------------------------- |
| `staining`        | `EntityReference`              | Staining identity associated with the training data.                   |
| `sample_basis`    | `Literal['current_at_export']` | Basis of the sample counts; v2 records samples current at export time. |
| `current_samples` | `SampleCounts`                 | Positive, negative, total, and slice counts at export time.            |
| `training_run`    | \`TrainingRun                  | None\`                                                                 |

## TrainingSample

Describe one positive or negative classifier training example.

Attributes:

| Name                         | Type                   | Description                                               |
| ---------------------------- | ---------------------- | --------------------------------------------------------- |
| `slice_id, slice_name`       |                        | Identifier and optional display name of the source slice. |
| `staining_id, staining_name` |                        | Identifier and display name of the classified staining.   |
| `cell_id`                    | \`int                  | None\`                                                    |
| `cell_detection_run_id`      | \`str                  | None\`                                                    |
| `label`                      | `Literal['on', 'off']` | Exported training label, "on" or "off".                   |
| `created_at`                 | `NormalizedDatetime`   | Sample creation time as a timezone-aware UTC datetime.    |

## ClassificationResultInfo

Describe one slice-level classification result before arrays are loaded.

Attributes:

| Name                   | Type                 | Description                                                   |
| ---------------------- | -------------------- | ------------------------------------------------------------- |
| `slice_id, slice_name` |                      | Identifier and optional display name of the classified slice. |
| `staining_id`          | `str`                | Identifier of the classified staining.                        |
| `classifier_id`        | `str`                | Identifier of the classifier used for this result.            |
| `source`               | `DetectionSource`    | Detection lineage that produced the classified cells.         |
| `on_count, off_count`  |                      | Exported positive and negative counts, or None.               |
| `threshold`            | \`float              | None\`                                                        |
| `timestamp`            | `NormalizedDatetime` | Result time as a timezone-aware UTC datetime.                 |
| `npz_path`             | `str`                | Archive path to the result arrays.                            |

## MatchResultInfo

Describe one slice-level cell-match result before arrays are loaded.

Attributes:

| Name                   | Type                 | Description                                                            |
| ---------------------- | -------------------- | ---------------------------------------------------------------------- |
| `slice_id, slice_name` |                      | Identifier and optional display name of the matched slice.             |
| `side_a, side_b`       |                      | Actual staining, detection-run, and unmatched count for each NPZ side. |
| `algorithm_version`    | `str`                | Matching algorithm version.                                            |
| `overlap_threshold`    | `float`              | Minimum overlap fraction used to retain candidate pairs.               |
| `timestamp`            | `NormalizedDatetime` | Result time as a timezone-aware UTC datetime.                          |
| `candidate_pair_count` | \`int                | None\`                                                                 |
| `matched_count`        | \`int                | None\`                                                                 |
| `npz_path`             | `str`                | Archive path to the match arrays.                                      |

## SliceExclusion

Explain why one slice has no classification or match result.

Attributes:

| Name          | Type  | Description                                          |
| ------------- | ----- | ---------------------------------------------------- |
| `slice_id`    | `str` | Identifier of the omitted slice.                     |
| `slice_name`  | \`str | None\`                                               |
| `reason_code` | `str` | Stable machine-readable omission category.           |
| `reason`      | `str` | Human-readable explanation recorded by the exporter. |

## SharedDetectionSource

Identify classification based on a shared cell-count detection.

Attributes:

| Name            | Type                          | Description                                 |
| --------------- | ----------------------------- | ------------------------------------------- |
| `kind`          | `Literal['shared_detection']` | Always "shared_detection".                  |
| `cell_count_id` | `str`                         | Identifier of the shared cell-count result. |

## IndependentDetectionSource

Identify classification based on a staining-specific detection.

Attributes:

| Name                    | Type                               | Description                                        |
| ----------------------- | ---------------------------------- | -------------------------------------------------- |
| `kind`                  | `Literal['independent_detection']` | Always "independent_detection".                    |
| `cell_detection_run_id` | `str`                              | Identifier of the staining-specific detection run. |

## Validation and limits

## ExportLimits

Configure resource limits for reading untrusted exports.

Attributes:

| Name                           | Type    | Description                                                                                                |
| ------------------------------ | ------- | ---------------------------------------------------------------------------------------------------------- |
| `max_members`                  | `int`   | Maximum number of archive members.                                                                         |
| `max_total_uncompressed_bytes` | `int`   | Maximum declared total uncompressed ZIP size in bytes. Extracted directories have no aggregate byte limit. |
| `max_metadata_bytes`           | `int`   | Maximum size of one JSON or JSONL metadata member in bytes.                                                |
| `max_compression_ratio`        | `float` | Maximum declared compression ratio of one ZIP member. This does not apply to extracted directories.        |

Notes

Path-safety and NumPy pickle protections remain mandatory.

## ValidationReport

Collect all independently detectable metadata validation issues.

Attributes:

| Name     | Type                          | Description                                                  |
| -------- | ----------------------------- | ------------------------------------------------------------ |
| `issues` | `tuple[ValidationIssue, ...]` | Validation issues. An empty tuple means the export is valid. |
| `valid`  | `bool`                        | True when :attr:issues is empty.                             |

### valid

```
valid: bool
```

Whether the export passed validation.

## ValidationIssue

Describe one actionable problem found in an export.

Attributes:

| Name      | Type  | Description                                            |
| --------- | ----- | ------------------------------------------------------ |
| `path`    | `str` | Root-relative member path associated with the problem. |
| `code`    | `str` | Stable machine-readable issue code.                    |
| `message` | `str` | Human-readable explanation.                            |
| `field`   | \`str | None\`                                                 |
