# Contributing

## Helping

This project is open to contributions. The following guide will help setup the environment. Thank you for considering.

## Setup

[Python](https://www.python.org/) `3.10+` is required to run this project. We strongly recommend using [uv](https://docs.astral.sh/uv/) to manage this project.

1. Fork the project

2. Clone the fork with `git`

    ```bash
    git clone https://github.com/GamerTuruu/DF-Metadata-Customizer.git
    cd DF-Metadata-Customizer
    ```

3. Install the project from `pyproject.toml`

    a. If using `uv`

    ```bash
    uv sync
    ```

    b. If using `pip`

    ```bash
    pip install -e .
    ```

4. Test running the application to ensure compatibility

    a. If using `uv`

    ```bash
    uv run df_metadata_customizer
    ```

    b. If using `pip`

    ```bash
    python df_metadata_customizer/__main__.py
    ```

## Pull Requests

After pushing changes to your fork, you can create a [Pull Request](https://github.com/GamerTuruu/DF-Metadata-Customizer/pulls)

## Releases

Releases are only managed by maintainers. Executables are built by the GitHub Action via pyinstaller. If you would like to build executables locally, run the following:

```bash
pyinstaller DFMetadataCustomizer.spec
```

and look in the `dist` folder.
