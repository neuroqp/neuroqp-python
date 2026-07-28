# Classification and matches

Classification data is available when `export.classification` is not `None`.

## Load classification results

```python
with open_export("project.zip") as export:
    module = export.classification
    if module is None:
        raise RuntimeError("classification module not included")

    classification = module.for_staining("NeuN")
    result = classification.load_result(export.slices[0])

    print(result.cell_ids.shape)
    print(result.centroids.shape)
    print(result.positive_centroids.shape)
```

`load_results()` concatenates all per-slice arrays and provides a read-only `by_slice` mapping:

```python
results = classification.load_results()
slice_result = results.by_slice["slice-id"]
```

## Training samples and omissions

Training samples are eager metadata:

```python
positive_samples = classification.find_training_samples(label="on")
omitted = classification.find_omitted_slices(reason_code="no_source")
```

## Load cell matches

```python
match = module.match("dapi-neun")
result = match.load_result("slice-id")

print(result.cell_ids_a)
print(result.cell_ids_b)
print(result.iou)
```

The SDK validates required array names, dtypes, shapes, lengths, finite values, masks, thresholds, and declared counts when results load. NumPy archives are always opened with `allow_pickle=False`.
