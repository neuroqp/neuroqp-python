---
name: neuroqp-python
description: Build, explain, or debug Python analyses of NeuroQP project exports. Use when working with NeuroQP ZIP exports or extracted export folders; navigating animals, slices, stainings, images, registrations, classifications, or cell matches; processing exported TIFF images; interpreting NeuroQP result arrays; or using the neuroqp Python package and CLI.
---

# NeuroQP Python

Help neuroscientists write reproducible analyses of NeuroQP project exports. Prefer the public `neuroqp` API, preserve the scientific meaning of exported data, and produce code that can be adapted from an example export to a real project with minimal changes.

## Check for updates

Once per task, run `scripts/check_updates.py --json` from this skill directory with the Python environment used by the analysis. If `notifications` is non-empty, show each notification in one short paragraph before continuing. Never update the package or skill automatically. If the check cannot run or reach the update service, continue without mentioning it.

## Establish the analysis

Identify the analysis environment and confirm the installed version:

```bash
python -c "import neuroqp; print(neuroqp.__version__)"
```

Set the export path once. Prefer the user's real export; otherwise use the documented example:

```python
from pathlib import Path

PROJECT_FILE = Path("path/to/project-export.zip")
```

Use `neuroqp inspect PROJECT_FILE` to discover project contents when the requested analysis depends on data that may be optional. Open the export with a context manager and keep storage-backed operations inside it:

```python
from neuroqp import open_export

with open_export(PROJECT_FILE) as export:
    print(export)
    for animal in export.animals:
        print(animal.name, animal.id)
```

ZIP archives and extracted export directories have the same object model. If a trusted ZIP exceeds the configured 4 GiB declared-uncompressed limit, instruct the user to extract it and pass the resulting folder to `open_export()`. Do not recommend extraction for unsafe-path, unsafe-link, or suspicious-compression failures.

## Navigate by IDs and discover by names

- Treat IDs as opaque, stable keys for joins.
- Use exact-name helpers for interactive work only when the name is unique.
- List available stainings, classifications, match `pair_key` values, and optional modules instead of guessing them.
- Check `export.registration` and `export.classification` for `None`.
- Keep the export open while following relationships or opening artifacts.
- Metadata records and already-loaded NumPy result arrays remain usable after the export closes.

```python
with open_export(PROJECT_FILE) as export:
    for animal in export.animals:
        for slice_ in animal.slices:
            print(animal.id, slice_.id, slice_.slice_coordinate_mm)

    if export.classification is not None:
        for classification in export.classification.classifications:
            print(classification.staining.name)
        for match in export.classification.matches:
            print(match.pair_key, match.staining_a.name, match.staining_b.name)
```

## Choose the relevant reference

- Read [scientific-results.md](references/scientific-results.md) before loading, joining, thresholding, or aggregating classification or cell-match results.
- Read [images-and-large-files.md](references/images-and-large-files.md) before decoding TIFFs, extracting centroid patches, processing many images, resizing images, or handling a large ZIP.
- Read [troubleshooting.md](references/troubleshooting.md) when validation fails, an object cannot be found, a context is closed, or exact current API details are needed.

## Scientific guardrails

- Preserve array row alignment; filter aligned arrays with the same mask.
- Treat centroids as `(x, y)` pixels in their declared source image or mask, not atlas coordinates.
- Do not assume two images or masks share a pixel grid merely because they belong to the same slice.
- Use exported `is_positive` values unless the analysis explicitly explores another threshold.
- Keep omitted slices separate from measured zeros.
- Use `(slice_id, cell_id)` as a classification-cell key because cell IDs can repeat across slices.
- Read match side metadata instead of inferring side A and B from a pair key.
- Aggregate at the experimental unit chosen by the study design; do not treat cells or slices as independent animals.
- Do not invent atlas transformations. The current package exposes registration metadata but does not yet transform classification centroids into atlas space.

## Write useful analysis code

- Start with a small inspection cell or script, then implement the requested analysis.
- Keep `PROJECT_FILE` as the main user-editable input.
- Preserve IDs, omission reasons, thresholds, source metadata, and relevant physical scale in analysis tables.
- Process large images one at a time and release temporary paths and memmaps promptly.
- Use established NumPy, pandas, tifffile, and scientific-image APIs rather than creating NeuroQP-specific replacements.
- Validate assumptions against the actual export and public object attributes before writing a large workflow.

For exact signatures or uncommon objects, use the installed package's `help()` and public attributes, then consult [llms.txt](https://python.neuroqp.com/llms.txt) or the complete [llms-full.txt](https://python.neuroqp.com/llms-full.txt). Prefer documentation matching the installed NeuroQP minor version when versioned pages are available.
