# Dependency specification

Dependencies for a project can be specified in various forms, which depend on the type
of the dependency and on the optional constraints that might be needed for it to be installed.

## Version constraints

### Caret requirements

**Caret requirements** allow SemVer compatible updates to a specified version.
An update is allowed if the new version number does not modify the left-most non-zero digit in the major, minor, patch grouping.
In this case, if we ran `poetry update requests`, poetry would update us to version `2.14.0` if it was available,
but would not update us to `3.0.0`.
If instead we had specified the version string as `^0.1.13`, poetry would update to `0.1.14` but not `0.2.0`.
`0.0.x` is not considered compatible with any other version.

Here are some more examples of caret requirements and the versions that would be allowed with them:

| Requirement | Versions allowed |
| ----------- | ---------------- |
| ^1.2.3      | >=1.2.3 <2.0.0   |
| ^1.2        | >=1.2.0 <2.0.0   |
| ^1          | >=1.0.0 <2.0.0   |
| ^0.2.3      | >=0.2.3 <0.3.0   |
| ^0.0.3      | >=0.0.3 <0.0.4   |
| ^0.0        | >=0.0.0 <0.1.0   |
| ^0          | >=0.0.0 <1.0.0   |

### Tilde requirements

**Tilde requirements** specify a minimal version with some ability to update.
If you specify a major, minor, and patch version or only a major and minor version, only patch-level changes are allowed.
If you only specify a major version, then minor- and patch-level changes are allowed.

`~1.2.3` is an example of a tilde requirement.

| Requirement | Versions allowed |
| ----------- | ---------------- |
| ~1.2.3      | >=1.2.3 <1.3.0   |
| ~1.2        | >=1.2.0 <1.3.0   |
| ~1          | >=1.0.0 <2.0.0   |

### Wildcard requirements

**Wildcard requirements** allow for the latest (dependency dependent) version where the wildcard is positioned.

`*`, `1.*` and `1.2.*` are examples of wildcard requirements.

| Requirement | Versions allowed |
| ----------- | ---------------- |
| *           | >=0.0.0          |
| 1.*         | >=1.0.0 <2.0.0   |
| 1.2.*       | >=1.2.0 <1.3.0   |

### Inequality requirements

**Inequality requirements** allow manually specifying a version range or an exact version to depend on.

Here are some examples of inequality requirements:

```text
>= 1.2.0
> 1
< 2
!= 1.2.3
```

### Exact requirements

You can specify the exact version of a package.
This will tell Poetry to install this version and this version only.
If other dependencies require a different version, the solver will ultimately fail and abort any install or update procedures.

#### Multiple requirements

Multiple version requirements can also be separated with a comma, e.g. `>= 1.2, < 1.5`.

## `git` dependencies

To depend on a library located in a `git` repository,
the minimum information you need to specify is the location of the repository with the git key:

```toml
[tool.poetry.dependencies]
requests = { git = "https://github.com/requests/requests.git" }
```

Since we haven’t specified any other information,
Poetry assumes that we intend to use the latest commit on the `master` branch
to build our project.

You can combine the `git` key with the `branch` key to use another branch.
Alternatively, use `rev` or `tag` to pin a dependency to a specific commit hash
or tagged ref, respectively. For example:

```toml
[tool.poetry.dependencies]
# Get the latest revision on the branch named "next"
requests = { git = "https://github.com/kennethreitz/requests.git", branch = "next" }
# Get a revision by its commit hash
flask = { git = "https://github.com/pallets/flask.git", rev = "38eb5d3b" }
# Get a revision by its tag
numpy = { git = "https://github.com/numpy/numpy.git", tag = "v0.13.2" }
```

## `path` dependencies

To depend on a library located in a local directory or file,
you can use the `path` property:

```toml
[tool.poetry.dependencies]
# directory
my-package = { path = "../my-package/", develop = false }

# file
my-package = { path = "../my-package/dist/my-package-0.1.0.tar.gz" }
```

!!!note

    Before poetry 1.1 directory path dependencies were installed in editable mode by default. You should set the `develop` attribute explicitly,
    to make sure the behavior is the same for all poetry versions.

## `url` dependencies

To depend on a library located on a remote archive,
you can use the `url` property:

```toml
[tool.poetry.dependencies]
# directory
my-package = { url = "https://example.com/my-package-0.1.0.tar.gz" }
```

with the corresponding `add` call:

```bash
poetry add https://example.com/my-package-0.1.0.tar.gz
```


## Python restricted dependencies

You can also specify that a dependency should be installed only for specific Python versions:

```toml
[tool.poetry.dependencies]
pathlib2 = { version = "^2.2", python = "~2.7" }
```

```toml
[tool.poetry.dependencies]
pathlib2 = { version = "^2.2", python = "~2.7 || ^3.2" }
```

## Using environment markers

If you need more complex install conditions for your dependencies,
Poetry supports [environment markers](https://www.python.org/dev/peps/pep-0508/#environment-markers)
via the `markers` property:

```toml
[tool.poetry.dependencies]
pathlib2 = { version = "^2.2", markers = "python_version ~= '2.7' or sys_platform == 'win32'" }
```


## Multiple constraints dependencies

Sometimes, one of your dependency may have different version ranges depending
on the target Python versions.

Let's say you have a dependency on the package `foo` which is only compatible
with Python <3.0 up to version 1.9 and compatible with Python 3.4+ from version 2.0:
you would declare it like so:

```toml
[tool.poetry.dependencies]
foo = [
    {version = "<=1.9", python = "^2.7"},
    {version = "^2.0", python = "^3.4"}
]
```

## Expanded dependency specification syntax

In the case of more complex dependency specifications, you may find that you
end up with lines which are very long and difficult to read. In these cases,
you can shift from using "inline table" syntax, to the "standard table" syntax.

An example where this might be useful is the following:

```toml
[tool.poetry.dev-dependencies]
black = {version = "19.10b0", allow-prereleases = true, python = "^3.6", markers = "platform_python_implementation == 'CPython'"}
```

As a single line, this is a lot to digest. To make this a little bit easier to
work with, you can do the following:

```toml
[tool.poetry.dev-dependencies.black]
version = "19.10b0"
allow-prereleases = true
python = "^3.6"
markers = "platform_python_implementation == 'CPython'"
```

All of the same information is still present, and ends up providing the exact
same specification. It's simply split into multiple, slightly more readable,
lines.

!!!note

    The constraints **must** have different requirements (like `python`)
    otherwise it will cause an error when resolving dependencies.
