# Validate an export

Validation returns every metadata issue it can safely identify in one report. This notebook downloads a small synthetic export so you can run it immediately. To validate your own data, change `PROJECT_FILE` to the path of your NeuroQP ZIP.

```python
from pathlib import Path
from urllib.request import urlretrieve

from neuroqp import validate_export

PROJECT_FILE = Path("neuroqp-example-v2.zip")  # Change this to your own project export.
EXAMPLE_URL = (
    "https://raw.githubusercontent.com/neuroqp/neuroqp-python/"
    "bc913cd/docs/assets/downloads/neuroqp-example-v2.zip"
)
if not PROJECT_FILE.is_file():
    urlretrieve(EXAMPLE_URL, PROJECT_FILE)

report = validate_export(PROJECT_FILE)
report
```

```
ValidationReport(issues=())
```

```python
assert report.valid
assert report.issues == ()
```
