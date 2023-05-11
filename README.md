# poetry-bin

This project builds [Poetry](https://github.com/python-poetry/poetry) Python dependency management tool into a binary executable using [PyOxidizer](https://github.com/indygreg/PyOxidizer).

The aim is to have a Poetry instance fully independent of the local Python environment. More details are available in the [dedicated blog post](https://dev.to/gi0baro/how-i-made-a-binary-version-of-poetry-package-manager-5246).

> **Note:** due to patches implemented over Poetry components, this build might introduce unwanted bugs over Poetry project, use at your own risk.

Due to its nature, `poetry-bin` has some key differences compared to the "vanilla version", specifically:

- `self` commands are dropped
- Plugins are not supported (yet?). The only included plugin is the `export` one
- the selection of the Python interpreter to use is slightly different, as it won't use `sys.executable` to make decisions

## Installation

You can install Poetry binary build using the install script:

    curl https://raw.githubusercontent.com/gi0baro/poetry-bin/master/install.sh | sh

or you might want to use [Homebrew](https://brew.sh/):

    brew install gi0baro/tap/poetry-bin

or you can manually download the packages from the [releases page](https://github.com/gi0baro/poetry-bin/releases).

> **Note:** x86 builds are available for Linux, MacOS and Windows platforms, arm64 builds are available for Linux and MacOS platforms.

## Docker images

Prebuilt docker images based on python ones with integrated `poetry` binaries are available [on the repository registry](https://github.com/gi0baro/poetry-bin/pkgs/container/poetry-bin). 

These images are produced weekly, and can be used like:

```Dockerfile
FROM ghcr.io/gi0baro/poetry-bin:3.10 as builder

COPY pyproject.toml .
COPY poetry.lock .
RUN poetry install --no-dev

FROM python:3.10-slim

COPY --from=builder /.venv /.venv
ENV PATH /.venv/bin:$PATH

WORKDIR /app
COPY . app

ENTRYPOINT [ "your_entrypoint" ]
CMD [ "your_command" ]
```

## Github action

A [Github action](https://github.com/gi0baro/setup-poetry-bin) is available on the [marketplace](https://github.com/marketplace/actions/setup-poetry-bin) and can be used in workflows:

```yaml
- name: Setup Poetry
  uses: gi0baro/setup-poetry-bin@v1
```
