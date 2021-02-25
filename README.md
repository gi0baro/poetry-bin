# poetry-bin

This project builds [Poetry](https://github.com/python-poetry/poetry) Python dependency management tool into a binary executable using [PyOxidizer](https://github.com/indygreg/PyOxidizer).

The aim is to have a Poetry instance which is fully independant of the local Python environment.

> **Note:** due to patches implemented over Poetry components, this build might introduce unwanted bugs over Poetry project, use at your own risk.

## Installation

You can install Poetry binary build using [Homebrew](https://brew.sh/):

    brew install gi0baro/poetry-bin/poetry-bin

or you can manually download the package from the [releases page](https://github.com/gi0baro/poetry-bin/releases).

> **Note:** only x86 builds for Linux and MacOS are currently available.
