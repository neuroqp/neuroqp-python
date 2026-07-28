# Object model

`ProjectExport` is the root of the reader-bound object graph:

```text
ProjectExport
├── animals → Animal → slices → Slice
│                         ├── images → Image
│                         ├── cell_mask → FileArtifact | None
│                         └── registration → SliceRegistration | None
├── stainings → Staining
├── atlas → Atlas | None
├── registration → Registration | None
└── classification → ClassificationModule | None
                          ├── classifications → Classification
                          └── matches → Match
```

## Reader-bound objects

Project objects offer navigation and raw-file access. They check that their export remains open:

```python
with open_export("project.zip") as export:
    slice_ = export.slices[0]
    metadata = slice_.metadata

print(metadata)  # Safe: immutable Pydantic record.
print(slice_.images)  # Raises ClosedExportError.
```

## Metadata records

Metadata models normalize wire names to Python names, timestamps to timezone-aware UTC `datetime` values, and collections to immutable tuples. Unknown additive fields remain available through Pydantic’s extra-field support.

## Result containers

Classification and match loaders return frozen dataclasses containing NumPy arrays. Their compact text representation is useful in a REPL, while notebooks receive a small HTML summary.
