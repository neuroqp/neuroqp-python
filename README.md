# NeuroQP Python

NeuroQP Python lets neuroscientists open a NeuroQP project export, navigate its animals, slices, stainings, images, and registrations, and analyze classification or cell-match results with Python and NumPy.

> **Status:** `0.1.0.dev0` is an unpublished release candidate for NeuroQP export format v2.

## Installation

Create and activate a virtual environment for your analysis:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the current release-candidate snapshot:

```bash
python -m pip install "https://github.com/neuroqp/neuroqp-python/archive/bc913cd.zip"
```

See the [installation guide](docs/getting-started/installation.md) for Windows instructions, JupyterLab setup, and the future PyPI installation command.

## Getting started

Validate or inspect an exported NeuroQP project:

```bash
neuroqp validate path/to/neuroqp_export.zip
neuroqp inspect path/to/neuroqp_export.zip
```

Open an export from Python:

```python
from neuroqp import open_export

with open_export("neuroqp_export.zip") as export:
    print(export)

    animal = export.animal_by_name("Mouse 1")
    for slice_ in animal.slices:
        print(slice_.name, slice_.slice_coordinate_mm)

    if export.classification is not None:
        classification = export.classification.for_staining("NeuN")
        results = classification.load_results()
        print(results.positive_centroids)
```

ZIP archives and extracted export directories are both supported. Continue with the [quickstart](docs/getting-started/quickstart.md), [analysis guide](docs/guides/classification.md), or [example notebooks](docs/examples/index.md).

## Project links

- [Documentation](https://python.neuroqp.com/)
- [AI-readable documentation](https://python.neuroqp.com/llms.txt)
- [Export v2 specification](https://python.neuroqp.com/latest/specifications/export-v2/)
- [Versions](https://github.com/neuroqp/neuroqp-python/tags)
- [Releases](https://github.com/neuroqp/neuroqp-python/releases)
- [Changelog](CHANGELOG.md)
- [Questions and support](https://github.com/neuroqp/neuroqp-python/discussions)
- [Issue tracker](https://github.com/neuroqp/neuroqp-python/issues)

## Supported versions

- Python 3.12 through 3.14
- NeuroQP project export format v2

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) if you want to work on the package itself.

## License

[MIT](LICENSE)
