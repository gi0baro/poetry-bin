# poetry-bin

This project builds [Poetry](https://github.com/python-poetry/poetry) Python dependency management tool into a binary executable using [PyOxidizer](https://github.com/indygreg/PyOxidizer).

The aim is to have a Poetry instance which is fully independant of the local Python environment.

> **Note:** due to patches implemented over Poetry components, this build might introduce unwanted bugs over Poetry project, use at your own risk.

## Installation

You can install Poetry binary build using the install script:

    curl https://raw.githubusercontent.com/gi0baro/poetry-bin/master/install.sh | sh

or you might want to use [Homebrew](https://brew.sh/):

    brew install gi0baro/tap/poetry-bin

or you can manually download the packages from the [releases page](https://github.com/gi0baro/poetry-bin/releases).

> **Note:** only x86 builds for Linux, MacOS and Windows are currently available.
