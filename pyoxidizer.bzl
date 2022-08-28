def force_fs_libs(policy, resource):
    for lib in ["certifi"]:
        if (
            resource.name == lib or
            resource.name.startswith("{}.".format(lib)) or (
                hasattr(resource, "package") and
                resource.package == lib
            )
        ):
            resource.add_location = "filesystem-relative:lib"

def make_exe():
    dist = default_python_distribution(python_version="3.10")

    policy = dist.make_python_packaging_policy()
    policy.resources_location_fallback = "filesystem-relative:lib"
    policy.register_resource_callback(force_fs_libs)

    config = dist.make_python_interpreter_config()
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
        for lib in ["virtualenv"]:
            if (
                resource.name == lib or
                resource.name.startswith("{}.".format(lib)) or (
                    hasattr(resource, "package") and
                    resource.package == lib
                )
            ):
                continue
        # skip wheels
        if resource.name.endswith(".whl"):
            continue
        exe.add_python_resource(resource)

    exe.add_python_resources(exe.read_package_root("vendor/poetry-core/src", ["poetry"]))
    exe.add_python_resources(exe.pip_install(["-r", "vendor/poetry-core/vendors/deps.txt"]))
    exe.add_python_resources(exe.pip_install(["./vendor/importlib_metadata"]))
    exe.add_python_resources(exe.pip_install(["./vendor/jsonschema"]))
    exe.add_python_resources(exe.pip_install(["./vendor/lark"]))

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
    entrypoint = "."
    files.add_python_resource(entrypoint, exe)
    return files

register_target("exe", make_exe)
register_target("resources", make_embedded_resources, depends=["exe"], default_build_script=True)
register_target("install", make_install, depends=["exe"], default=True)

resolve_targets()
