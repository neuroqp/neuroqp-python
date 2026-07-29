# Images and masks

NeuroQP exports the image artifacts referenced by the project snapshot. These are the files stored by NeuroQP at export time, not a guarantee of untouched microscope acquisition data. `original_filename` records the uploaded filename; `archive_path` identifies the exact copy inside the export.

TIFF decoding, LZW support, and region selection are included with NeuroQP Python. The package gives `tifffile` safe access to the exported file while leaving pixel-processing choices under your control.

## Choose an access method

| Goal                                             | Recommended method                                      | Memory and disk behavior                                 |
| ------------------------------------------------ | ------------------------------------------------------- | -------------------------------------------------------- |
| Inspect dimensions, dtype, pages, or compression | `TiffFile(image.open())`                                | Reads TIFF metadata without decoding the complete image  |
| Load a small complete image                      | `imread(image.open())`                                  | Allocates the complete decoded array in RAM              |
| Process a large complete image                   | `page.asarray(out=...)`                                 | Decodes to a disk-backed NumPy memmap                    |
| Extract a few patches                            | `imread(path, selection=...)` through `image.as_path()` | Decodes only strips intersecting each region             |
| Extract many patches from one image              | Decode once to a memmap, then slice it                  | Uses disk instead of repeatedly decoding the same strips |
| Apply an incremental algorithm                   | `page.segments()`                                       | Yields one decoded strip at a time                       |
| Process every project image                      | Handle one image at a time                              | Bounds peak memory and temporary-disk use                |

`image.size_bytes` is the encoded TIFF-file size. It does not predict decoded memory. TIFF compression can make a small stored file expand into a much larger pixel array.

## Inspect image metadata without decoding pixels

Images are grouped by slice and staining. Open the TIFF header to inspect the actual stored array:

```
from math import prod
from pathlib import Path

from tifffile import TiffFile

from neuroqp import open_export

PROJECT_FILE = Path("path/to/project-export.zip")

with open_export(PROJECT_FILE) as export:
    image = export.slices[0].images[0]
    with image.open() as stream, TiffFile(stream) as tif:
        page = tif.pages[0]
        decoded_bytes = prod(page.shape) * page.dtype.itemsize
        print("filename:", image.metadata.original_filename)
        print("stored bytes:", image.size_bytes)
        print("pages:", len(tif.pages))
        print("shape:", page.shape)
        print("dtype:", page.dtype)
        print("compression:", page.compression)
        print("estimated decoded bytes:", decoded_bytes)
```

The estimate covers one page and does not include temporary arrays created by your analysis. TIFF files may contain channels, pages, or other leading dimensions, so inspect `page.shape` rather than assuming a two-dimensional array.

## Load a small complete image

Use this approach only when the decoded array and the arrays created by your analysis comfortably fit in memory:

```
from tifffile import imread

with open_export(PROJECT_FILE) as export:
    image = export.slices[0].images[0]
    with image.open() as stream:
        pixels = imread(stream)

print(pixels.shape, pixels.dtype)
```

The NumPy array owns its pixels and remains usable after the export closes. For a two-dimensional image, NeuroQP `(x, y)` coordinates index the array as `pixels[y, x]`.

## Decode a large image to disk

A compressed, strip-based TIFF cannot be memory-mapped directly. Decode it once into a raw disk-backed array when the complete image is needed but should not occupy RAM:

```
from pathlib import Path

import numpy as np
from tifffile import TiffFile

SCRATCH = Path("analysis-scratch")
SCRATCH.mkdir(exist_ok=True)
DECODED_FILE = SCRATCH / "decoded-image.memmap"

with open_export(PROJECT_FILE) as export:
    image = export.slices[0].images[0]
    with image.as_path(directory=SCRATCH) as image_path:
        with TiffFile(image_path) as tif:
            pixels = tif.pages[0].asarray(out=str(DECODED_FILE))

        assert isinstance(pixels, np.memmap)
        print(pixels.shape, pixels.dtype)
        # Run analysis while pixels is open.
        pixels.flush()
        del pixels
```

For a ZIP export, `image.as_path()` first copies the encoded TIFF into `SCRATCH` and removes that copy when the context exits. `DECODED_FILE` is separate and remains until you delete it. Plan disk space for both files plus analysis outputs. For an extracted export, `image.as_path()` yields the existing TIFF without copying it.

## Extract a few patches

For a small number of regions, use TIFF/Zarr selection. Coordinates below are array bounds in `(y, x)` order:

```
from tifffile import imread

SCRATCH.mkdir(exist_ok=True)

with open_export(PROJECT_FILE) as export:
    image = export.slices[0].images[0]
    with image.as_path(directory=SCRATCH) as image_path:
        patch = imread(
            image_path,
            selection=(slice(500, 756), slice(1000, 1256)),
        )

print(patch.shape)
```

NeuroQP TIFFs are normally LZW-compressed and organized in horizontal strips rather than tiles. A region read avoids unrelated strips, but every intersecting strip is decoded across its full width. Repeated patch reads from the same strips can therefore perform much more work than their patch dimensions suggest.

## Extract many centroid patches

When extracting many patches from one image, decode the image once to a disk-backed array and slice that array repeatedly. Group classification results by source image or slice before moving to the next TIFF.

```
from pathlib import Path

from tifffile import TiffFile

PATCH_RADIUS = 32
DECODED_FILE = SCRATCH / "centroid-source.memmap"

with open_export(PROJECT_FILE) as export:
    image = export.slices[0].images[0]
    classification = export.classification
    if classification is None:
        raise RuntimeError("This export has no classification module.")

    result = classification.classifications[0].load_result(image.slice.id)
    with image.as_path(directory=SCRATCH) as image_path:
        with TiffFile(image_path) as tif:
            pixels = tif.pages[0].asarray(out=str(DECODED_FILE))

        height, width = pixels.shape[:2]
        patches = {}
        for cell_id, (x, y) in zip(result.cell_ids, result.centroids, strict=True):
            x_center = round(float(x))
            y_center = round(float(y))
            x0 = max(0, x_center - PATCH_RADIUS)
            x1 = min(width, x_center + PATCH_RADIUS)
            y0 = max(0, y_center - PATCH_RADIUS)
            y1 = min(height, y_center + PATCH_RADIUS)
            patches[int(cell_id)] = pixels[y0:y1, x0:x1].copy()

        del pixels
```

Only combine centroids with an image known to use the same pixel grid. A shared-detection result refers to the shared cell mask; an independent-detection result refers to its staining-specific source. Matching slice IDs alone does not prove pixel alignment.

## Process strips incrementally

Use `segments()` when an algorithm can consume independent horizontal blocks and does not require the complete image:

```
from tifffile import TiffFile

with open_export(PROJECT_FILE) as export:
    image = export.slices[0].images[0]
    with image.as_path(directory=SCRATCH) as image_path:
        with TiffFile(image_path) as tif:
            for decoded_strip, position, shape in tif.pages[0].segments():
                print(position, shape, decoded_strip.mean())
```

Strip processing requires explicit boundary and position handling. Prefer a disk-backed complete decode when the algorithm needs neighbouring rows across strip boundaries or global image context.

## Process every image

Keep the export open, but finish each image before opening the next:

```
from tifffile import TiffFile

with open_export(PROJECT_FILE) as export:
    for slice_ in export.slices:
        for image in slice_.images:
            with image.open() as stream, TiffFile(stream) as tif:
                page = tif.pages[0]
                print(slice_.id, image.id, page.shape, page.dtype)
            # Decode or materialize this image here, write its result, then
            # release its arrays and temporary files before continuing.
```

Do not accumulate complete decoded images for the entire project unless their combined decoded size has been measured and intentionally fits your resources.

## Determine the pixel size

Pixel size is project metadata associated with the whole-slice and detail-image labels:

```
with open_export(PROJECT_FILE) as export:
    image = export.slices[0].images[0]
    magnification = image.metadata.magnification

    if magnification == export.project.whole_slice_label:
        microns_per_pixel = export.project.whole_slice_microns_per_pixel
    elif magnification == export.project.detail_image_label:
        microns_per_pixel = export.project.detail_microns_per_pixel
    else:
        microns_per_pixel = None

    print(magnification, microns_per_pixel)
```

Treat `None` as an unrecognized or custom image label. Do not infer physical scale from the filename. Classification centroids remain in source-image or mask pixels; multiplying by a pixel size converts distances but does not perform atlas registration.

## Load the cell mask

A slice may contain the shared cell-count detection mask:

```
from tifffile import imread

with open_export(PROJECT_FILE) as export:
    slice_ = export.slices[0]
    mask_artifact = slice_.cell_mask

    if mask_artifact is None:
        print("No cell mask was exported for this slice.")
    else:
        with mask_artifact.open() as stream:
            cell_mask = imread(stream)
        print(cell_mask.shape, cell_mask.dtype)
```

The mask is copied into the export without decoding or transformation. For a classification result with `metadata.source.kind == "shared_detection"`, its `cell_ids` refer to labels in this shared mask. An `independent_detection` result uses a staining-specific detection source and must not be joined to this mask by cell ID. Compare shapes before overlaying data; do not assume that every image or detection source for a slice uses the same pixel grid.

## Resize or convert an image

NeuroQP Python deliberately returns standard NumPy arrays instead of owning a resize or conversion API. Use an established scientific-image library after opening or decoding the TIFF.

- Record the interpolation method, output shape, and resulting physical pixel size.
- Use anti-aliasing when downsampling continuous intensity images.
- Preserve dtype and value range unless the analysis explicitly requires normalization.
- Resize label masks only with nearest-neighbour interpolation; other interpolation creates nonexistent label values.
- Keep a lossless TIFF or another analysis-appropriate scientific format for quantitative work. Treat JPEG and other lossy formats as visualization outputs, not analysis sources.

For exceptional files without a high-level object, use the [low-level access guide](https://python.neuroqp.com/0.1/guides/low-level/index.md).
