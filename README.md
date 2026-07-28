# NeuroQP Python

NeuroQP Python is the Python SDK and command-line interface for reading, validating, and working with NeuroQP project exports.

> **Status:** `0.1.0.dev0` is an early development version. It supports the structural metadata of canonical v2 exports; scientific result loading and the complete navigation API are not available yet.

## Installation

The package has not been published to PyPI yet. To use the current development version from a source checkout:

```bash
uv sync
```

## Getting started

Validate or inspect an exported NeuroQP project:

```bash
uv run neuroqp validate path/to/neuroqp_export.zip
uv run neuroqp inspect path/to/neuroqp_export.zip
uv run neuroqp inspect path/to/neuroqp_export.zip --json
```

Open an export from Python:

```python
from neuroqp import open_export

with open_export("neuroqp_export.zip") as export:
    print(export.project.name)
    print(export.animals)
```

ZIP archives and extracted export directories are both supported.

## Project links

- [Documentation: export v2 specification](docs/specifications/export-v2.md)
- [Versions](https://github.com/neuroqp/neuroqp-python/tags)
- [Releases](https://github.com/neuroqp/neuroqp-python/releases)
- [Issue tracker](https://github.com/neuroqp/neuroqp-python/issues)
- [Source code](https://github.com/neuroqp/neuroqp-python)

Versioned user and API documentation links will be added when the documentation site is published.

## Supported versions

- Python 3.10 through 3.14
- NeuroQP project export format v2

## Development

See [AGENTS.md](AGENTS.md) for the minimal development commands and repository rules.

## License

[MIT](LICENSE)
