# Object model

`ProjectExport` is the starting point for navigating a project:

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

## Keep the export open while navigating

Use `open_export()` as a context manager. Objects such as animals, slices, images, registrations, classifications, matches, and file artifacts use the open ZIP or directory to follow relationships and load files.

```python
from pathlib import Path

from neuroqp import open_export

PROJECT_FILE = Path("path/to/project-export.zip")

with open_export(PROJECT_FILE) as export:
    animal = export.animals[0]
    slice_ = animal.slices[0]
    image = slice_.images[0]
    print(animal.name, slice_.name, image.staining.name)
```

When the `with` block ends, the export closes automatically. Further navigation or file loading raises `ClosedExportError`:

```python
from neuroqp import ClosedExportError

try:
    print(slice_.images)
except ClosedExportError:
    print("The export is already closed.")
```

## Data you can keep after closing

Copy or load the information needed for later analysis while the export is open:

| Safe after closing | Examples |
| --- | --- |
| Metadata records | `slice_.metadata`, `image.metadata`, `export.project` |
| Plain Python values | IDs, names, dictionaries, lists, numbers |
| Loaded scientific results | `classification.load_result(...)`, `classification.load_results()` |
| Loaded image data | Encoded bytes, a decoded NumPy array, or a separately stored memmap |

```python
with open_export(PROJECT_FILE) as export:
    slice_ = export.slices[0]
    slice_metadata = slice_.metadata
    project_metadata = export.project

    image = slice_.images[0]
    image_metadata = image.metadata
    with image.open() as stream:
        image_bytes = stream.read()

print(project_metadata.name)
print(slice_metadata.name, image_metadata.original_filename)
print(len(image_bytes))
```

Metadata records are immutable snapshots. They remain safe because they do not need to read another export member. Loaded result containers own their NumPy arrays, so those arrays also remain available after closing.

Streams returned by `open()` and paths yielded by `as_path()` are storage-backed resources. Open and consume them inside the parent export context. For ZIP exports, an `as_path()` path is a temporary copy and disappears when its own context exits. A memmap remains usable only while its separately decoded backing file exists.

## Data that still needs the open export

Keep the context open for:

- moving between animals, slices, stainings, images, registrations, classifications, and matches;
- calling `image.open()`, `image.as_path()`, `artifact.open()`, `artifact.as_path()`, or `export.member()`;
- loading classification or match arrays that have not yet been read;
- listing raw archive members.

For a long notebook analysis, it is fine to keep one `with open_export(...)` block around the cells that navigate and load data. For repeated functions, open the export inside the function or pass an already-open export and call the function before the context closes.
