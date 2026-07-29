# Validate and inspect

Use `validate` to check whether an export can be opened safely. Use `inspect` when you also want a readable project summary.

## Inspect an export

```bash
neuroqp inspect neuroqp-example-v2.zip
```

Example output:

```text
Validation
  Status: valid
  Source: neuroqp-example-v2.zip

Export
  Format: v2
  ID: export-1
  Exported: 2026-07-28T12:00:00+00:00
  Expires: 2026-08-04T12:00:00+00:00

Project
  Name: Minimal project
  ID: project-1
  Type: 10x
  Whole-slice image: 4x (4.2975 µm/pixel)
  Detail image: 10x (1.719 µm/pixel)

Modules
  data: included
  registration: not included
  classification: not included

Atlas
  None

Contents
  Animals: 1
    - Mouse 1 (animal-1)
  Slices: 1
  Stainings: 1
    - DAPI (staining-1)
  Brain regions: 1
    - Central medial nucleus of the thalamus (CM, 599)

Classifier selections
  None
```

The sections mean:

| Section | Meaning |
| --- | --- |
| Validation | Whether metadata validation passed and which file or directory was inspected |
| Export | Export-format version, snapshot identity, creation time, and expiry recorded by NeuroQP |
| Project | Project identity, imaging labels, and physical pixel sizes |
| Modules | Which data, registration, and classification modules were requested and included |
| Atlas | Atlas identity and version, or `None` when no atlas is included |
| Contents | Counts plus human-readable names and IDs for key project objects |
| Classifier selections | Selected classifier ID for each staining when classification data is included |

`inspect` validates before displaying metadata. For an invalid export it prints the validation issues instead of a partial project summary.

## Inspect as JSON

Use JSON when a script, workflow manager, or data inventory needs the summary:

```bash
neuroqp inspect neuroqp-example-v2.zip --json
```

The current JSON structure is:

```json
{
  "valid": true,
  "source": "neuroqp-example-v2.zip",
  "exportVersion": "v2",
  "exportId": "export-1",
  "exportedAt": "2026-07-28T12:00:00+00:00",
  "expiresAt": "2026-08-04T12:00:00+00:00",
  "project": {
    "id": "project-1",
    "name": "Minimal project",
    "type": "10x",
    "atlasId": null,
    "comments": null,
    "wholeSlice": {
      "label": "4x",
      "micronsPerPixel": 4.2975
    },
    "detailImage": {
      "label": "10x",
      "micronsPerPixel": 1.719
    }
  },
  "atlas": null,
  "modules": ["data"],
  "counts": {
    "animals": 1,
    "slices": 1,
    "stainings": 1,
    "brainRegions": 1
  },
  "animals": [
    {"id": "animal-1", "name": "Mouse 1"}
  ],
  "stainings": [
    {"id": "staining-1", "name": "DAPI"}
  ],
  "brainRegions": [
    {
      "structureId": 599,
      "name": "Central medial nucleus of the thalamus",
      "acronym": "CM"
    }
  ],
  "selectedClassifierHeadIdsByStaining": {},
  "linkedTrainingRunIdsByStaining": {}
}
```

`atlas` is either `null` or an object with `id`, `key`, `version`, and `name`. Collection fields are always arrays, mapping fields are always objects, and timestamps are ISO 8601 strings with a timezone offset.

When the export is invalid, `inspect --json` returns the validation structure shown below instead of the project-summary structure.

## Validate an export

```bash
neuroqp validate path/to/project.zip
```

A valid export produces:

```text
Valid NeuroQP v2 export: path/to/project.zip
```

An invalid export lists every issue that can be discovered safely in the same pass:

```text
Invalid NeuroQP export: path/to/project.zip
- project/slices.json [0.animalId]: slice references unknown animal animal-99 (unknown_animal)
- data/slices/slice-1/images.json [0.archivePath]: archivePath must be data/slices/slice-1/images/image-1__cells.tif (invalid_archive_path)
```

Each issue contains:

- `path`: the file or archive member where the problem was found;
- `field`: the specific JSON field or array name when available;
- `message`: a human-readable explanation;
- `code`: a stable machine-readable category.

Common issue codes and responses:

| Code or family | What it usually means | What to do |
| --- | --- | --- |
| `not_found`, `invalid_container` | The path is wrong, the download is incomplete, or the file is not a readable ZIP | Check the path and download the export again |
| `missing_member` | A required metadata, image, mask, or result file is absent | Create a new export; do not manually assemble missing members |
| `invalid_json`, `invalid_utf8`, `invalid_field` | Metadata is malformed or a required value has the wrong type | Re-export the project and report the issue if it repeats |
| `unsupported_version` | The package does not support this export-format version | Upgrade NeuroQP Python or use documentation for the exported version |
| `duplicate_*` | An ID, name, archive member, image, or result appears more than allowed | Re-export; this is an inconsistent snapshot |
| `invalid_reference`, `unknown_*` | Metadata points to an animal, slice, staining, image, or result that is absent | Re-export and report the repeated consistency error |
| `inconsistent_*`, `invalid_archive_path` | Two records disagree about an identity, path, atlas, or slice | Re-export and report the repeated consistency error |
| `unsafe_path`, `unsafe_link` | The container includes a path or link that could escape the export | Do not open or extract it; obtain a fresh export |
| `size_limit` | A ZIP declares more than the default 4 GiB of uncompressed members | If it is a trusted NeuroQP export, extract it and pass the resulting folder to `open_export()` |
| `member_limit` | The container contains more files than the configured safety limit | Confirm that the source is a genuine export before changing the limit |
| `compression_limit` | A ZIP member has a suspicious declared compression ratio | Do not extract it or disable the check; obtain a fresh trusted export |
| `invalid_npz`, `invalid_array`, `array_length` | A classification or match result archive has missing or incompatible arrays | Create a new export and report the result-generation problem |
| `threshold_mismatch`, `count_mismatch`, `index_mismatch`, `invalid_fraction`, `duplicate_cell_id` | Scientific result arrays disagree with their exported metadata or invariants | Do not analyze that result; re-export and report the problem |

Use `--json` to receive the same validation result as structured data:

```bash
neuroqp validate path/to/project.zip --json
```

```json
{
  "valid": false,
  "issues": [
    {
      "path": "project/slices.json",
      "field": "0.animalId",
      "code": "unknown_animal",
      "message": "slice references unknown animal animal-99"
    }
  ]
}
```

Both commands return exit status `0` for a valid export and `1` for an invalid export.

## Validate from Python

`validate_export()` returns a report instead of raising for validation problems:

```python
from pathlib import Path

from neuroqp import validate_export

PROJECT_FILE = Path("path/to/project-export.zip")

report = validate_export(PROJECT_FILE)
if report.valid:
    print("The export is valid.")
else:
    for issue in report.issues:
        location = f"{issue.path} [{issue.field}]" if issue.field else issue.path
        print(location, issue.code, issue.message)
```

Metadata, cross-references, container safety, and result indexes are checked during `validate_export()`. Classification and match NPZ arrays remain lazy and are checked when `load_result()` or `load_results()` reads them.

## Resource limits

Use `ExportLimits` only when a trusted export has unusually large metadata or an unusual number of members:

```python
from neuroqp import ExportLimits, validate_export

limits = ExportLimits(max_metadata_bytes=16 * 1024**2)
report = validate_export(PROJECT_FILE, limits=limits)
```

Path-safety checks and NumPy pickle protection cannot be disabled.

The 4 GiB default applies to the total declared uncompressed size of ZIP members, not to extracted directories. For a larger trusted ZIP, prefer extracting it and opening the resulting folder instead of increasing `max_total_uncompressed_bytes`. Directory exports retain member, metadata, path, link, and pickle protections without an aggregate file-size check.
