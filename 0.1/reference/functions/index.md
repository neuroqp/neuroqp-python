# Entry points

## open_export

```
open_export(
    source: str | Path,
    *,
    limits: ExportLimits | None = None,
) -> ProjectExport
```

Open and validate a local v2 ZIP archive or extracted directory.

Parameters:

| Name     | Type           | Description | Default                                                                                                        |
| -------- | -------------- | ----------- | -------------------------------------------------------------------------------------------------------------- |
| `source` | \`str          | Path\`      | Path to a NeuroQP export ZIP archive or extracted directory.                                                   |
| `limits` | \`ExportLimits | None\`      | Optional resource limits for archive and metadata reads. Mandatory path and pickle protections remain enabled. |

Returns:

| Type            | Description                         |
| --------------- | ----------------------------------- |
| `ProjectExport` | The open, validated project export. |

Raises:

| Type                      | Description                                  |
| ------------------------- | -------------------------------------------- |
| `InvalidExportError`      | If the export fails validation.              |
| `UnsupportedVersionError` | If the export format version is unsupported. |

Notes

Use the returned object as a context manager so its storage is closed promptly. If a trusted ZIP exceeds the configured total uncompressed size, extract it and pass the resulting directory instead; directory exports have no aggregate byte limit.

## validate_export

```
validate_export(
    source: str | Path,
    *,
    limits: ExportLimits | None = None,
) -> ValidationReport
```

Validate a local v2 ZIP archive or extracted directory.

Parameters:

| Name     | Type           | Description | Default                                                                                                        |
| -------- | -------------- | ----------- | -------------------------------------------------------------------------------------------------------------- |
| `source` | \`str          | Path\`      | Path to a NeuroQP export ZIP archive or extracted directory.                                                   |
| `limits` | \`ExportLimits | None\`      | Optional resource limits for archive and metadata reads. Mandatory path and pickle protections remain enabled. |

Returns:

| Type               | Description                                        |
| ------------------ | -------------------------------------------------- |
| `ValidationReport` | An aggregate report. A valid export has no issues. |
