import importlib.resources

from distlib import resources as _res_patch_target


class Resource:
    def __init__(self, pkg, name):
        self.pkg = pkg
        self.name = name

    @property
    def bytes(self):
        return importlib.resources.read_binary(self.pkg, self.name)


class ResourceWrapper:
    def __init__(self, pkg):
        self._pkg = pkg

    def find(self, name):
        return Resource(self._pkg, name)


def finder(pkg):
    return ResourceWrapper(pkg)


setattr(_res_patch_target, "finder", finder)
