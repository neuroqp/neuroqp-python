# NeuroQP Python

Python SDK for reading and working with NeuroQP project exports.

The current `0.1.0.dev0` foundation safely opens and validates canonical v2
exports from local ZIP files or extracted directories.

```bash
uv sync --all-groups
uv run neuroqp validate path/to/neuroqp_export.zip
uv run neuroqp inspect path/to/neuroqp_export.zip --json
```

```python
from neuroqp import open_export

with open_export("neuroqp_export.zip") as export:
    print(export.project.name)
    print(export.animals)
```

The normative wire contract is
[`docs/specifications/export-v2.md`](docs/specifications/export-v2.md).
Scientific result loading and the complete navigation API are not part of this
first implementation phase.

