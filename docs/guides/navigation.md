# Navigate a project

Set the export path once at the start of your script or notebook:

```python
from pathlib import Path

from neuroqp import open_export

PROJECT_FILE = Path("path/to/project-export.zip")
```

## Start by listing what is available

Names are convenient for exploration, while IDs are the reliable keys for lookups and joins. IDs are opaque strings: store and compare them, but do not infer scientific meaning from their format.

```python
with open_export(PROJECT_FILE) as export:
    print("Project:", export.name, export.id)

    for animal in export.animals:
        print("Animal:", animal.name, animal.id)

    for staining in export.stainings:
        print("Staining:", staining.name, staining.id)

    for region in export.brain_regions:
        print("Region:", region.name, region.acronym, region.structure_id)
```

Use an ID when you already have one:

```python
with open_export(PROJECT_FILE) as export:
    animal = export.animal("animal-id")
    slice_ = export.slice("slice-id")
    staining = export.staining("staining-id")
    region = export.brain_region(599)
```

Use a name when it is more natural for an interactive analysis:

```python
with open_export(PROJECT_FILE) as export:
    animal = export.animal_by_name("Mouse 1")
    staining = export.staining_by_name("NeuN")
```

`animal_by_name()` and `staining_by_name()` require an exact, unique name. They raise `ObjectNotFoundError` when nothing matches and `AmbiguousNameError` when several objects have that name.

## Move from animals to slices

Each slice belongs to one animal. Iterate through `animal.slices` when the animal is your experimental unit:

```python
with open_export(PROJECT_FILE) as export:
    for animal in export.animals:
        for slice_ in animal.slices:
            print(animal.name, slice_.name, slice_.slice_coordinate_mm, slice_.id)
```

To search across the complete project, use `find_slices()`. It returns a tuple because slice names do not have to be unique:

```python
with open_export(PROJECT_FILE) as export:
    matching_slices = export.find_slices(name="Slice 1")
    for slice_ in matching_slices:
        print(slice_.animal.name, slice_.id)
```

Slice-name matching is exact. Prefer `slice.id` when keeping results for later joins.

## Find stainings and images

`find_stainings()` is useful when spelling, capitalization, or punctuation varies. For example, `"D-A P_I"` matches `"DAPI"`. It still returns every match rather than assuming the name is unique.

```python
with open_export(PROJECT_FILE) as export:
    dapi_matches = export.find_stainings("D-A P_I")
    for staining in dapi_matches:
        print(staining.name, staining.id)
```

Images belong to slices. Filter them by a staining object, staining ID, exact staining name, magnification label, original filename, or any combination:

```python
with open_export(PROJECT_FILE) as export:
    staining = export.staining_by_name("NeuN")

    for slice_ in export.slices:
        for image in slice_.find_images(staining=staining, magnification="10x"):
            print(slice_.name, image.metadata.original_filename, image.metadata.width, image.metadata.height)
```

Use `slice_.image("image-id")` when you already know the unique image ID. Continue with [Images and masks](images.md) to load image pixels and interpret their scale.

## Find brain regions

Atlas structure IDs are the unique brain-region keys. Name and acronym filters return tuples because labels are not treated as unique identifiers:

```python
with open_export(PROJECT_FILE) as export:
    region = export.brain_region(599)
    cm_regions = export.find_brain_regions(acronym="CM")
    named_regions = export.find_brain_regions(name="Central medial nucleus of the thalamus")
```

Brain-region metadata describes the project annotation set. It does not assign cells or image coordinates to regions.

## Check optional modules

Registration and classification are optional. Check them before navigating their contents:

```python
with open_export(PROJECT_FILE) as export:
    if export.registration is not None:
        print("Atlas:", export.registration.atlas.name)

    if export.classification is not None:
        for classification in export.classification.classifications:
            print("Classification:", classification.staining.name)
        for match in export.classification.matches:
            print("Match:", match.pair_key, match.staining_a.name, match.staining_b.name)
```

An absent module is `None`; an empty collection means the module was included but contains no objects of that kind.
