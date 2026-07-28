# Navigate a project

## Look up animals and slices

```python
with open_export("project.zip") as export:
    animal = export.animal("animal-id")
    animal = export.animal_by_name("Mouse 1")

    slice_ = export.slice("slice-id")
    matching = export.find_slices(name="Slice 1")
```

Singular lookups raise `ObjectNotFoundError` when there is no match and `AmbiguousNameError` when a name is not unique.

## Find stainings and images

```python
with open_export("project.zip") as export:
    staining = export.staining_by_name("NeuN")

    for slice_ in export.slices:
        images = slice_.find_images(staining=staining, magnification="10x")
        for image in images:
            print(image.metadata.width, image.metadata.height)
```

Staining lookup by `find_stainings()` ignores case and punctuation. Image filters can use a staining object, staining ID, or staining name.

## Open artifacts

```python
with open_export("project.zip") as export:
    image = export.slices[0].images[0]
    with image.open() as stream:
        image_bytes = stream.read()

    manifest = export.member("manifest.json")
    with manifest.open() as stream:
        manifest_bytes = stream.read()
```

The SDK returns bytes and does not decode TIFF images in v0.1.
