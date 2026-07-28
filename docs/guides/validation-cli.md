# Validate and inspect

## Command line

Validate an export:

```bash
neuroqp validate path/to/project.zip
```

Inspect valid metadata in human-readable sections:

```bash
neuroqp inspect path/to/project.zip
```

Use stable JSON output for scripts:

```bash
neuroqp validate path/to/project.zip --json
neuroqp inspect path/to/project.zip --json
```

Both commands return exit status `0` for a valid export and `1` for an invalid export.

## Python validation

`validate_export()` aggregates metadata issues instead of stopping at the first problem:

```python
from neuroqp import validate_export

report = validate_export("project.zip")
if not report.valid:
    for issue in report.issues:
        print(f"{issue.path}: {issue.message} ({issue.code})")
```

Binary result invariants are checked when the corresponding NPZ file is loaded.

## Resource limits

Use `ExportLimits` to lower or raise documented resource limits:

```python
from neuroqp import ExportLimits, validate_export

limits = ExportLimits(max_metadata_bytes=16 * 1024**2)
report = validate_export("project.zip", limits=limits)
```

Path-safety and NumPy pickle protections cannot be disabled.
