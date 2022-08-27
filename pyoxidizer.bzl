def make_exe():
    dist = default_python_distribution(python_version="3.10")

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

    for resource in exe.pip_install(["./vendor/poetry"]):
        # skip patched packages
        if resource.name == "poetry.core" or resource.name.startswith("poetry.core."):
            continue
        if resource.name == "requests" or resource.name.startswith("requests."):
            continue
        if resource.name == "virtualenv" or resource.name.startswith("virtualenv."):
            continue
        # skip wheels
        if resource.name.endswith(".whl"):
            continue
        exe.add_python_resource(resource)

    exe.add_python_resources(exe.read_package_root("vendor/poetry-core/src", ["poetry"]))
    exe.add_python_resources(exe.pip_install(["-r", "vendor/poetry-core/vendors/deps.txt"]))
    exe.add_python_resources(exe.pip_install(["./vendor/importlib_metadata"]))
    exe.add_python_resources(exe.pip_install(["./vendor/jsonschema"]))
    exe.add_python_resources(exe.pip_install(["./vendor/requests"]))

    for resource in exe.pip_install(["./vendor/virtualenv"]):
        # skip wheels
        if resource.name.endswith(".whl"):
            continue
        exe.add_python_resource(resource)

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

register_target("exe", make_exe)
register_target("resources", make_embedded_resources, depends=["exe"], default_build_script=True)
register_target("install", make_install, depends=["exe"], default=True)

resolve_targets()
