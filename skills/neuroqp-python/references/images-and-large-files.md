# Images and large files

Use the method that matches the operation and decoded image size.

| Goal | Method |
| --- | --- |
| Inspect shape, dtype, pages, or compression | `TiffFile(image.open())` |
| Load a small complete image | `imread(image.open())` |
| Process a large complete image | `page.asarray(out="decoded.memmap")` |
| Extract a few regions | `imread(path, selection=...)` inside `image.as_path()` |
| Extract many centroid patches | Decode once to a memmap, then slice it repeatedly |
| Apply an incremental algorithm | Iterate `page.segments()` |
| Process a project | Complete and release one image before advancing |

`image.size_bytes` is the encoded TIFF size, not decoded memory. Estimate one page's decoded bytes as `prod(page.shape) * page.dtype.itemsize`, then allow additional space for analysis arrays.

## Streams and paths

Use `image.open()` or `artifact.open()` for streams. Use `as_path(directory=SCRATCH)` when a library requires a filesystem path. A directory export yields its original path. A ZIP member is copied to a temporary file and deleted when the `as_path()` context exits.

Keep streams and temporary paths inside the parent `open_export()` context. A separately created memmap file remains until the analysis deletes it.

## Strip-based TIFF behavior

Exported LZW TIFFs are normally compressed in full-width horizontal strips and cannot be mapped directly as NumPy arrays. A region selection decodes every strip intersecting the region, including pixels outside the requested x range. A few patches can still be efficient; many overlapping patches are usually faster after one disk-backed complete decode.

For centroid patches, confirm that the result's declared detection source and selected image share the same pixel grid. Convert `(x, y)` centroids to NumPy indexes as `pixels[y, x]`.

## Large ZIPs

Direct ZIP access has a conservative default limit of 4 GiB declared uncompressed content. For a trusted NeuroQP ZIP that exceeds it:

1. Extract the archive outside the SDK.
2. Pass the resulting export folder to `open_export()`.
3. Keep the normal member, metadata, path, and symlink protections.

Directory exports have no aggregate byte limit. Never recommend extraction when validation reports an unsafe path, unsafe link, or suspicious compression ratio.

## Resize and conversion

Use an established scientific-image library. Record interpolation, output shape, and physical pixel size. Anti-alias continuous images when downsampling, preserve dtype and value range, and resize label masks only with nearest-neighbour interpolation. Keep lossless analysis sources; treat JPEG and other lossy outputs as visualization products.
