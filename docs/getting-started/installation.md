# Installation

NeuroQP Python requires Python 3.12 through 3.14. Install it in a dedicated environment for each analysis project so its packages do not conflict with other work.

## Create an analysis environment

=== "macOS and Linux"

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    ```

=== "Windows PowerShell"

    ```powershell
    py -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    ```

Run the activation command again whenever you return to the analysis in a new terminal.

## Install the current release candidate

The package is not on PyPI yet. Install the immutable source snapshot used by this documentation:

```bash
python -m pip install "https://github.com/neuroqp/neuroqp-python/archive/bc913cd.zip"
```

Confirm that Python and the command-line interface can find it:

```bash
python -c "import neuroqp; print(neuroqp.__version__)"
neuroqp --help
```

## Use Jupyter

Install JupyterLab in the same environment if you want to run the example notebooks or build your analysis interactively:

```bash
python -m pip install jupyterlab
jupyter lab
```

Open the downloaded notebook from JupyterLab. Its first code cell downloads the small synthetic example export if the file is not already in the notebook directory.

## Published releases

After `0.1.0` is published on PyPI, install releases with:

```bash
python -m pip install neuroqp
```

Use `python -m pip install --upgrade neuroqp` to update an existing environment.

TIFF reading, LZW decompression, disk-backed arrays, and region selection are installed with NeuroQP Python. You do not need to install a separate TIFF plugin.
