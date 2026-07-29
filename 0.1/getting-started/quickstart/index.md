# Quickstart

Download the [synthetic v2 export](https://python.neuroqp.com/0.1/assets/downloads/neuroqp-example-v2.zip) or use a ZIP exported from NeuroQP.

## Open a project

```
from neuroqp import open_export

with open_export("neuroqp-example-v2.zip") as export:
    print(export)
    print(export.name)
    print(export.version)
```

`open_export()` accepts a ZIP archive or an extracted export directory. It validates the archive before returning a `ProjectExport`.

## Navigate objects

```
with open_export("neuroqp-example-v2.zip") as export:
    animal = export.animal_by_name("Mouse 1")

    for slice_ in animal.slices:
        print(slice_.name, slice_.slice_coordinate_mm)
        for image in slice_.images:
            print(image.staining.name, image.metadata.original_filename)
```

Reader-bound objects remain usable only while the export is open. Pydantic metadata records and loaded NumPy results can be retained after the context manager exits.

## Validate without opening

```
from neuroqp import validate_export

report = validate_export("neuroqp-example-v2.zip")
print(report.valid)

for issue in report.issues:
    print(issue.path, issue.code, issue.message)
```

Continue with the [object-navigation guide](https://python.neuroqp.com/0.1/guides/navigation/index.md) or run the [executable notebooks](https://python.neuroqp.com/0.1/examples/index.md).
