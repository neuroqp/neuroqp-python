# Project exports

A NeuroQP project export is either a ZIP archive or an extracted directory with the same member tree. The root `manifest.json` identifies the format version, project, included modules, and paths to common metadata.

## Eager metadata, lazy arrays

Opening an export reads and validates JSON and JSONL metadata. Images, masks, classification arrays, and match arrays remain inside the storage container until code explicitly opens or loads them.

This boundary keeps normal navigation fast:

```python
with open_export("project.zip") as export:
    result_info = export.classification.classifications[0].result_index
    # No result NPZ has been loaded yet.
```

## Optional modules

The v2 format can contain three modules:

| Module | Python access | Content |
| --- | --- | --- |
| `data` | `export.slices`, `slice.images` | Project metadata and image artifacts |
| `registration` | `export.registration` | Atlas identity, landmarks, and detail transforms |
| `classification` | `export.classification` | Classifiers, samples, classification results, and matches |

An absent optional module is represented by `None`. Do not infer module availability from individual files.

## Compatibility

The SDK currently supports export v2. The [v2 specification](../specifications/export-v2.md) is normative. When a future version is added, current documentation will retain every supported specification and point “current” to the newest one.
