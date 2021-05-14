def make_dist():
    return default_python_distribution(python_version="3.9")

def make_exe(dist):
    policy = dist.make_python_packaging_policy()
    policy.resources_location_fallback = "filesystem-relative:lib"

    config = dist.make_python_interpreter_config()
    if not VARS.get("WIN_BUILD"):
        config.module_search_paths = ["$ORIGIN/../lib"]
    else:
        config.module_search_paths = ["$ORIGIN/lib"]
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
    if not VARS.get("WIN_BUILD"):
        entrypoint = "bin"
    else:
        entrypoint = "."
    files.add_python_resource(entrypoint, exe)
    return files

# def make_msi(exe):
#     return exe.to_wix_msi_builder(
#         "poetry-bin",
#         "Poetry",
#         "1.0",
#         # The author/manufacturer of your application.
#         ""
#     )


register_target("dist", make_dist)
register_target("exe", make_exe, depends=["dist"])
register_target("resources", make_embedded_resources, depends=["exe"], default_build_script=True)
register_target("install", make_install, depends=["exe"], default=True)
# register_target("msi_installer", make_msi, depends=["exe"])

resolve_targets()

PYOXIDIZER_VERSION = "0.16.0"
PYOXIDIZER_COMMIT = "4053178f2ba11d29f497d171289cb847cd07ed77"
