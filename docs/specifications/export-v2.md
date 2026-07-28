# NeuroQP project export v2

Status: normative. Wire version: `v2`.
Source of truth: the live NeuroQP exporter

This document defines the archive produced by the NeuroQP exporter and accepted
by the Python SDK. It was derived from
`apps/web/convex/projectExportWorker.ts`,
`algorithms/project_export_worker/handler.py`, the classification result
producers, and a post-fix v2 export generated on 28 July 2026. If the exporter
and this document disagree, fix this document and the SDK together from the
exporter behavior.

## Compatibility policy

NeuroQP owns wire-format versions. A new format is introduced in NeuroQP first.
The SDK then adds a private adapter, a synthetic fixture, contract tests, and a
new versioned specification before a package release advertises support.

- The newest supported format is the default.
- Every previously supported format and specification remains available.
- Public SDK models are stable and normalized; wire models and adapters are
  private.
- Unknown additive JSON fields are preserved and do not make an otherwise valid
  export invalid.
- Removing support for a published format is exceptional and requires a major
  SDK version.
- Published documentation snapshots are immutable.

The v2 SDK accepts only the canonical image layout described below. The
temporary pre-fix layout without both `imageId` and `archivePath` is not v2.

## Container and paths

An export is either the ZIP file produced by NeuroQP or an extracted directory
with the same member paths. ZIP member names use `/` separators and are relative
to the archive root. Members must not be absolute, contain `.` or `..` path
segments, use backslashes, repeat another member name, or be symbolic links.
Directory inputs must not resolve through a link outside their root.

All JSON is UTF-8. Generated JSON is pretty-printed, but whitespace and object
key order are not significant. JSON Lines files contain one UTF-8 JSON object
per non-empty line. Binary source objects retain their original bytes.

## Archive tree

```text
manifest.json
project/
  export.json
  project.json
  stainings.json
  animals.json
  slices.json
  brain-regions.json
data/                                                   # data module
  slices/{sliceId}/
    slice.json
    images.json
    images/{imageId}__{sanitizedOriginalFilename}
    detection/cell-mask.tif                             # optional per slice
registration/                                           # registration module
  atlas/atlas-manifest.json                             # when an atlas exists
  slices/{sliceId}/
    atlas-registration.json                             # optional per slice
    detail-to-whole-slice.json                          # optional per slice
classification/                                         # classification module
  manifest.json
  stainings/{stainingId}/
    classifier.json
    training/summary.json
    training/samples.jsonl
    results/index.json
    results/slices/{sliceId}.npz
  matches/{pairKey}/
    match.json
    slices/{sliceId}.npz
```

`manifest.json` and every `project/*.json` member are always present. Module
directories exist only when their module is listed in `includedModules`.
Individual registration, mask, classification result, and match members are
conditional on the corresponding source artifact being available.

The ZIP contains generated metadata and copied source objects. It is not a
database backup. Image members are the processed image artifacts referenced by
the export snapshot; the original filename and extension are retained in the
member name after sanitizing `/` and `\` to `_`. Classifier model weights and
other secret model artifacts are not exported.

## Common metadata

### `manifest.json`

| Field | Type | Meaning |
| --- | --- | --- |
| `exportVersion` | string | Required; exactly `"v2"`. |
| `exportId` | string | Export database identifier. |
| `exportedAt` | ISO 8601 string | UTC export creation time. |
| `project` | object | `{id, slug, name}` strings. |
| `projectMetadataPath` | string | Exactly `project/export.json`. |
| `includedModules` | string[] | Ordered subset of `data`, `registration`, `classification`. |
| `atlas` | object or null | `{id, key, version, name}` when configured. |
| `selectedClassifierHeadIdsByStaining` | object | Staining ID to selected classifier-head ID. |
| `linkedTrainingRunIdsByStaining` | object | Staining ID to training-run ID or null. |

### `project/export.json`

| Field | Type | Meaning |
| --- | --- | --- |
| `exportVersion` | string | Exactly `"v2"`. |
| `exportedAt` | ISO 8601 string | UTC export creation time. |
| `exportId` | string | Same value as the root manifest. |
| `projectId` | string | Same value as `manifest.project.id`. |
| `expiresAt` | integer | Source export expiry as Unix milliseconds. |
| `requestedModules` | string[] | Same module set as `includedModules`. |
| `selectedClassifierHeadIdsByStaining` | object | Same selection map as the root manifest. |

### `project/project.json`

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `name` | string | no | Project name. |
| `type` | string | no | Imaging/project type. |
| `atlasId` | string | yes | Configured atlas database ID. |
| `wholeSliceLabel` | string | no | Human label for the whole-slice image. |
| `wholeSliceMicronsPerPixel` | number | no | Whole-slice pixel size. |
| `detailImageLabel` | string | no | Human label for detail images. |
| `detailMicronsPerPixel` | number | no | Detail-image pixel size. |
| `comments` | string | yes | Project comments. |

### Project collections

`project/stainings.json` is an array of:

| Field | Type | Meaning |
| --- | --- | --- |
| `_id` | string | Staining database ID. |
| `name` | string | Canonical staining name. |

`project/animals.json` is an array of:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `_id` | string | no | Animal database ID. |
| `name` | string | no | Animal name. |
| `comments` | string | yes | Comments. |
| `sex` | string | yes | Stored sex value. |
| `group` | string | yes | Resolved group name, not a database ID. |
| `condition` | string | yes | Resolved condition name, not a database ID. |

`project/slices.json` is an array of:

| Field | Type | Meaning |
| --- | --- | --- |
| `_id` | string | Slice database ID. |
| `animalId` | string | Parent animal database ID. |
| `apMm` | number | Anterior-posterior coordinate in millimetres. |

`project/brain-regions.json` is an array of:

| Field | Type | Meaning |
| --- | --- | --- |
| `structureId` | integer | Atlas structure ID. |
| `name` | string | Region name. |
| `acronym` | string | Region acronym. |

IDs are opaque strings. Consumers must not infer meaning from their shape.

## Data module

For every project slice, `data/slices/{sliceId}/slice.json` contains `_id`,
`animalId`, `apMm`, and nullable `name`. Its first three values match the
corresponding entry in `project/slices.json`.

`data/slices/{sliceId}/images.json` is an array of:

| Field | Type | Meaning |
| --- | --- | --- |
| `imageId` | string | Image database ID; required in canonical v2. |
| `archivePath` | string | Exact root-relative image member; required in canonical v2. |
| `height` | integer | Image height in pixels. |
| `width` | integer | Image width in pixels. |
| `stainingId` | string | Referenced staining ID. |
| `sliceId` | string | Parent slice ID. |
| `magnification` | string | Stored magnification label. |
| `originalFilename` | string | Original uploaded filename. |

`archivePath` is exactly
`data/slices/{sliceId}/images/{imageId}__{sanitizedOriginalFilename}` and must
name an archive member. `sliceId` must match the containing directory and
`stainingId` must exist in `project/stainings.json`. Image IDs and archive paths
are unique within the export.

`detection/cell-mask.tif` is present only when the slice has a cell-count mask.
It is copied without decoding or transformation.

## Registration module

`registration/atlas/atlas-manifest.json` repeats `id`, `key`, `version`, and
`name`, and adds `species`, `plane`, and the complete additive atlas `spec`
object. The current atlas specification includes raster dimensions and pixel
size, AP origin/spacing, coordinate metadata, physical/raster transforms,
asset paths, species, organ, plane, slice count, and leaf-region count. The
outer atlas identity must agree with the root manifest.

`atlas-registration.json` contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `slideId` | string | Slice ID matching its directory. |
| `apMm` | number | Registered AP coordinate in millimetres. |
| `pointsV2` | object[] | Landmarks with `imageXPx`, `imageYPx`, `atlasPlaneXMm`, `atlasPlaneYMm`. |

`detail-to-whole-slice.json` contains `slideId` plus `corners`, an ordered array
of `{x, y}` pixel coordinates. Registration and alignment files are independent
and either may be absent for a slice.

## Classification module

### Manifest and classifier metadata

`classification/manifest.json` has `exportVersion: "v2"`, `stainings`, and
`matches`. Each staining entry contains:

- `staining: {id, name}` and `classifier: {id, displayName}`;
- `classifierPath`, `trainingSummaryPath`, `trainingSamplesPath`, and
  `resultIndexPath`, each naming an existing member;
- `exclusions`, an array of `{sliceId, sliceName, reasonCode, reason}`.

Each match entry contains `pairKey`, `stainingA`, `stainingB`, `matchPath`, and
the same exclusion shape.

`classifier.json` contains classifier `id`, `displayName`, numeric `version`,
`headType`, `source` (`trained`, `platform_import`, or `project_import`),
numeric-millisecond `createdAt`, nullable `comments`, `{id, name}` `staining`,
nullable `trainingRunId`, and additive `evaluationMetrics`. It deliberately
does not contain model weights, model URLs, recipe hashes, or secret metadata.

### Training data

`training/summary.json` contains `{id, name}` `staining`,
`sampleBasis: "current_at_export"`, `currentSamples` (`on`, `off`, `total`,
`sliceCount`), and nullable `trainingRun`. A training run may contain:

- `id`, `status`, `trainingDurationMs`;
- `finalMetrics` (`accuracy`, `precision`, `recall`, `f1`, `trainLoss`,
  `valLoss`, `sampleCount`);
- `recordedSampleCounts`;
- numeric-array `histories`;
- `coverage`, `confidence`, and `convergence` metric objects.

Every `training/samples.jsonl` row contains `sliceId`, nullable `sliceName`,
`stainingId`, `stainingName`, nullable numeric `cellId`, optional
`cellDetectionRunId`, `label` (`on` or `off`), and numeric-millisecond
`createdAt`. The file may be empty.

### Classification result index and NPZ

`results/index.json` contains `staining`, `classifier`, and a `slices` array.
Each slice entry contains:

- `sliceId`, `sliceName`, `stainingId`, and `classifierId`;
- `sourceLineage`, either
  `{kind: "shared_detection", cellCountId}` or
  `{kind: "independent_detection", cellDetectionRunId}`;
- nullable `onCount`, `offCount`, and `threshold`;
- numeric-millisecond `timestamp`;
- `npzPath`, which exactly names the slice result member.

Classification NPZ members use these arrays:

| Array | Shape | Dtype | Meaning |
| --- | --- | --- | --- |
| `cell_ids` | `(N,)` | `int32` | Cell label IDs. |
| `centroids_x` | `(N,)` | `float32` | X pixel coordinates. |
| `centroids_y` | `(N,)` | `float32` | Y pixel coordinates. |
| `intensities` | `(N,)` | `float32` | Classifier probabilities. |
| `is_on` | `(N,)` | `uint8` | Authoritative positive mask, values 0 or 1. |
| `threshold` | `(1,)` | `float32` | Classification threshold. |
| `staining` | `(1,)` | legacy object or Unicode | Redundant staining name. |

All length-`N` arrays align by index. Required numeric arrays must be loadable
with `numpy.load(..., allow_pickle=False)`. Some existing v2 files contain a
legacy object-dtype `staining` array; consumers must tolerate the member but
must never access it. Staining identity comes from JSON. New producers should
write Unicode. `onCount + offCount == N`; when counts and threshold are present,
`is_on` agrees with `intensities >= threshold`.

### Match index and NPZ

`matches/{pairKey}/match.json` contains `pairKey`, `stainingA`, `stainingB`,
`exclusions`, and `slices`. A slice entry contains `sliceId`, `sliceName`,
`sideA` and `sideB` staining/detection identities and nullable unmatched
counts, `algorithmVersion`, `overlapThreshold`, numeric-millisecond
`timestamp`, nullable `candidatePairCount` and `matchedCount`, and `npzPath`.
The side order records the actual NPZ orientation and may differ from the
lexical staining order.

Match NPZ members use scalar `schema_version` (`int32`),
`algorithm_version` (Unicode), and `overlap_threshold` (`float32`), plus aligned
`(M,)` arrays:

- `cell_ids_a`, `cell_ids_b`, `intersection_area`, `area_a`, and `area_b`
  (`int32`);
- `overlap_fraction_a`, `overlap_fraction_b`, `overlap_fraction_min`, and
  `iou` (`float32`);
- when `M > 0`, `centroids_x_a`, `centroids_y_a`, `centroids_x_b`, and
  `centroids_y_b` (`float32`).

Each cell ID occurs at most once per side. Fractions and IoU are in `[0, 1]`;
`overlap_fraction_min` is at least the indexed overlap threshold.

## Required invariants

A conforming reader validates at least:

1. the safe container/path rules and configured resource limits;
2. all common members and supported `exportVersion`;
3. parseable UTF-8 JSON with the required field types;
4. agreement of export IDs, project IDs, versions, module sets, and selection
   maps between common metadata files;
5. unique IDs where they are keys and valid animal, staining, slice, atlas,
   classifier, and member-path references;
6. canonical `imageId`/`archivePath` pairs and exact image-member existence;
7. module manifests and indexed member paths when a module is included;
8. NPZ safety, dtype, shape, alignment, counts, and threshold invariants when
   binary results are loaded.

Validation issues have a member `path`, optional field or array name, stable
machine-readable `code`, and human-readable `message`. Readers should aggregate
independent metadata issues rather than stop at the first malformed field.

## Security and limits

Exports are untrusted input. Readers must never extract a ZIP to inspect it and
must always use `allow_pickle=False`. They reject path traversal, absolute or
duplicate members, backslash aliases, links, corrupt containers, unsafe
required object arrays, and resource-limit violations.

Default SDK limits are 10,000 members, 4 GiB total declared uncompressed ZIP
size, 8 MiB per JSON/JSONL member, and a 1,000:1 per-member compression ratio.
Callers may provide a documented `ExportLimits` override; there is no switch
that disables all safety checks.

## Minimal example

```json
{
  "exportVersion": "v2",
  "exportId": "export-1",
  "exportedAt": "2026-07-28T12:00:00Z",
  "project": {"id": "project-1", "slug": "demo", "name": "Demo"},
  "projectMetadataPath": "project/export.json",
  "includedModules": ["data"],
  "atlas": null,
  "selectedClassifierHeadIdsByStaining": {},
  "linkedTrainingRunIdsByStaining": {}
}
```
The corresponding data image record is canonical only when it includes both:

```json
{
  "imageId": "image-1",
  "archivePath": "data/slices/slice-1/images/image-1__demo.tif"
}
```
