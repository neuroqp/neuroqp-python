# Troubleshooting and exact API details

## Validate before debugging analysis code

Run:

```bash
neuroqp validate path/to/project-export.zip
neuroqp inspect path/to/project-export.zip
```

Use `--json` for structured output. Common responses:

| Issue | Response |
| --- | --- |
| `not_found`, `invalid_container` | Check the path or obtain a complete export |
| `missing_member`, `invalid_json`, `unknown_*`, `inconsistent_*` | Re-export and report a repeated problem |
| `unsupported_version` | Upgrade NeuroQP Python or use documentation for that export version |
| `unsafe_path`, `unsafe_link`, `compression_limit` | Do not extract or weaken checks; obtain a fresh export |
| `size_limit` | Extract a trusted large ZIP and open the resulting folder |
| `invalid_npz`, `invalid_array`, `threshold_mismatch`, `invalid_fraction` | Do not analyze the affected result; re-export and report it |

`validate_export()` checks container safety, metadata, and cross-references. Lazy NPZ arrays are validated when `load_result()` or `load_results()` reads them.

## Object lookup

- Prefer IDs for durable lookups and joins.
- Exact-name helpers can raise `ObjectNotFoundError` or `AmbiguousNameError`.
- Name-search helpers can return several results.
- Match pair keys are opaque; list `export.classification.matches`.
- Optional modules are `None`; an empty collection means the module exists but contains no objects.

## Closed exports

`ClosedExportError` means code followed a relationship or opened a file after the parent `open_export()` context ended. Move that work into the context, or copy metadata and load required arrays before closing it. Do not retain ZIP streams or temporary `as_path()` paths.

## Current API details

Do not guess methods from this skill. First inspect the installed package:

```python
import neuroqp

print(neuroqp.__version__)
help(neuroqp.open_export)
```

Then use:

- Documentation index: <https://python.neuroqp.com/llms.txt>
- Complete AI-readable documentation: <https://python.neuroqp.com/llms-full.txt>
- Human documentation: <https://python.neuroqp.com/>

Prefer the immutable documentation matching the installed package's major and minor version.
