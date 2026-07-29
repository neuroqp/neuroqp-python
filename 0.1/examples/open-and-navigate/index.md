# Open and navigate an export

This notebook downloads a small synthetic v2 export so you can run every cell immediately. When you are ready to analyze your own data, change `PROJECT_FILE` to the path of your NeuroQP ZIP.

```python
from pathlib import Path
from urllib.request import urlretrieve

from neuroqp import open_export

PROJECT_FILE = Path("neuroqp-example-v2.zip")  # Change this to your own project export.
EXAMPLE_URL = (
    "https://raw.githubusercontent.com/neuroqp/neuroqp-python/"
    "bc913cd/docs/assets/downloads/neuroqp-example-v2.zip"
)
if not PROJECT_FILE.is_file():
    urlretrieve(EXAMPLE_URL, PROJECT_FILE)
```

```python
with open_export(PROJECT_FILE) as export:
    project_summary = export
    animal = export.animals[0]
    slice_ = animal.slices[0]
    image = slice_.images[0]

project_summary, animal, slice_, image
```

```
(ProjectExport(name='Minimal project', id='project-1', version='v2', animals=1, slices=1, stainings=1, modules=('data',), closed=True),
 Animal(id='animal-1', name='Mouse 1', slices=1),
 Slice(id='slice-1', name='Slice 1', animal_id='animal-1', slice_coordinate_mm=-1.25, images=1),
 Image(id='image-1', filename='minimal.tif', staining_id='staining-1', shape=(2, 2)))
```

```python
with open_export(PROJECT_FILE) as export:
    rows = [
        (slice_.name, image.staining.name, image.metadata.original_filename)
        for slice_ in export.slices
        for image in slice_.images
    ]

rows
```

```
[('Slice 1', 'DAPI', 'minimal.tif')]
```
