# Installation

NeuroQP Python requires Python 3.12 through 3.14. Install it in a dedicated environment for each analysis project so its packages do not conflict with other work.

## Install NeuroQP Python

Choose the environment tool you already use. pip is available with Python; uv additionally records the analysis dependencies and their resolved versions.

Create and activate a virtual environment, then install NeuroQP Python.

**macOS and Linux**

```
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install neuroqp
```

**Windows PowerShell**

```
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install neuroqp
```

Run the activation command again whenever you return to the analysis in a new terminal. If you already have an active environment, only run `python -m pip install neuroqp`.

Confirm the installation:

```
python -c "import neuroqp; print(neuroqp.__version__)"
neuroqp --help
```

Initialize the analysis directory with Python 3.14 and add NeuroQP Python. uv creates and maintains the project’s `.venv` and `uv.lock`.

```
uv init --python 3.14
uv add neuroqp
```

Run commands in that environment without activating it:

```
uv run python -c "import neuroqp; print(neuroqp.__version__)"
uv run neuroqp --help
```

## Use Jupyter

Install JupyterLab in the same environment if you want to run the example notebooks or build your analysis interactively.

```
python -m pip install jupyterlab
jupyter lab
```

```
uv add jupyterlab
uv run jupyter lab
```

Open the downloaded notebook from JupyterLab. Its first code cell downloads the small synthetic example export if the file is not already in the notebook directory.

## Update NeuroQP Python

```
python -m pip install --upgrade neuroqp
```

```
uv lock --upgrade-package neuroqp
uv sync
```

TIFF reading, LZW decompression, disk-backed arrays, and region selection are installed with NeuroQP Python. You do not need to install a separate TIFF plugin.
