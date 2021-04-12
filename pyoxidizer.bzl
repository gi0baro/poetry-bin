def make_dist():
    return default_python_distribution(python_version="3.9")

def make_config_posix(dist):
    python_config = dist.make_python_interpreter_config()
    python_config.module_search_paths = ["$ORIGIN/../lib"]
    return python_config

def make_config_win(dist):
    python_config = dist.make_python_interpreter_config()
    python_config.module_search_paths = ["$ORIGIN/lib"]
    return python_config

def make_exe(dist, config):
    policy = dist.make_python_packaging_policy()
    policy.resources_location_fallback = "filesystem-relative:lib"

    config.run_module = "poetry.console.application"

    exe = dist.to_python_executable(
        name="poetry",
        packaging_policy=policy,
        config=config,
    )
    exe.add_python_resources(exe.pip_install(["./vendor/poetry"]))
    exe.add_python_resources(exe.read_package_root("vendor/certifi", ["certifi"]))
    exe.add_python_resources(exe.read_package_root("vendor/poetry-core", ["poetry"]))
    exe.add_python_resources(exe.pip_install(["./vendor/virtualenv"]))
    exe.add_python_resources(exe.pip_install(["./vendor/importlib_metadata"]))

    return exe

def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    files = FileManifest()
    files.add_python_resource("bin", exe)
    return files


register_target("dist", make_dist)
register_target("config_posix", make_config_posix, depends=["dist"])
register_target("config_win", make_config_win, depends=["dist"])
register_target("exe_posix", make_exe, depends=["dist", "config_posix"])
register_target("exe_win", make_exe, depends=["dist", "config_win"])
register_target("resources_posix", make_embedded_resources, depends=["exe_posix"], default_build_script=True)
register_target("install_posix", make_install, depends=["exe_posix"], default=True)
register_target("install_win", make_install, depends=["exe_win"])

resolve_targets()

PYOXIDIZER_VERSION = "0.11.0"
PYOXIDIZER_COMMIT = "UNKNOWN"
