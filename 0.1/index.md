# Build your own NeuroQP analyses in Python.

Open a NeuroQP project export, navigate animals, slices, stainings, and atlas registrations, then work directly with classification and cell-match results as NumPy arrays.

[Quickstart](https://python.neuroqp.com/0.1/getting-started/quickstart/index.md) [Browse the API](https://python.neuroqp.com/0.1/reference/functions/index.md)

```
from neuroqp import open_export

with open_export("neuroqp_export.zip") as export:
    print(export)
    print(export.animals[0].slices)
```

NeuroQP Python connects your NeuroQP project to your own scientific analysis. It keeps animals, slices, stainings, images, atlas registrations, classifications, and matched cells linked, so you can focus on quantifying, comparing, and visualizing results with the Python tools you already use.

## Start with real data

Install the package and open a ZIP archive or extracted directory.

[Installation →](https://python.neuroqp.com/0.1/getting-started/installation/index.md)

## Understand the objects

Move from a project to animals, slices, images, and optional results.

[Object model →](https://python.neuroqp.com/0.1/concepts/object-model/index.md)

## Analyze your results

Load classification and cell-match results for your own analysis.

[Classification guide →](https://python.neuroqp.com/0.1/guides/classification/index.md)
