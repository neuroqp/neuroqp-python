# Low-level access

The high-level object graph should cover normal analysis. Use [Images and masks](https://python.neuroqp.com/0.1/guides/images/index.md) for exported image data. Use raw member access when you need bytes that the SDK deliberately does not interpret.

## List archive members

```
with open_export("project.zip") as export:
    for path in sorted(export.members):
        print(path)
```

## Read one member

```
with open_export("project.zip") as export:
    artifact = export.member("manifest.json")
    print(artifact.size_bytes)
    with artifact.open() as stream:
        payload = stream.read()
```

Each `open()` call returns an independent binary stream. Directory members are read directly from their existing files; ZIP members are decompressed as the stream is read.

If a library requires a filesystem path, use `as_path()`:

```
from pathlib import Path

SCRATCH = Path("analysis-scratch")
SCRATCH.mkdir(exist_ok=True)

with open_export("project.zip") as export:
    artifact = export.member("data/slices/slice-1/images/image-1__cells.tif")
    with artifact.as_path(directory=SCRATCH) as path:
        use_library_that_requires_a_path(path)
```

An extracted export yields its existing member path. A ZIP member is copied into a temporary directory under `SCRATCH` and removed when the context exits.

## Keep the safety boundary

Do not use raw access to bypass validation or to load NumPy object arrays. If a supported v2 member is missing from the high-level API, open an issue rather than depending on private modules such as `neuroqp._reader`.
