# Installation

NeuroQP Python requires Python 3.10 through 3.14.

## Development release

The package is not on PyPI yet. Clone the repository and create the managed virtual environment:

```bash
git clone https://github.com/neuroqp/neuroqp-python.git
cd neuroqp-python
uv sync
```

Run Python or the CLI inside that environment:

```bash
uv run python
uv run neuroqp --help
```

If you prefer to activate the environment:

```bash
source .venv/bin/activate
python
```

## Published releases

After `0.1.0` is published, the normal installation command will be:

```bash
python -m pip install neuroqp
```

The PyPI command above is intentionally not active for the current development version.
