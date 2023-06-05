from __future__ import annotations

from collections import OrderedDict
from importlib.metadata import entry_points


class PluginLoader:
    _OPTIONS = None
    _ENTRY_POINTS = None

    @classmethod
    def entry_points_for(cls, key):
        return OrderedDict((e.name, e.load()) for e in cls.entry_points().get(key, {}))

    @classmethod
    def entry_points(cls):
        if cls._ENTRY_POINTS is None:
            cls._ENTRY_POINTS = entry_points()
        return cls._ENTRY_POINTS


class ComponentBuilder(PluginLoader):
    def __init__(self, interpreter, parser, name, possible):
        self.interpreter = interpreter
        self.name = name
        self._impl_class = None
        self.possible = possible
        self.parser = parser.add_argument_group(title=name)
        self.add_selector_arg_parse(name, list(self.possible))

    @classmethod
    def options(cls, key):
        if cls._OPTIONS is None:
            cls._OPTIONS = cls.entry_points_for(key)
        return cls._OPTIONS

    def add_selector_arg_parse(self, name, choices):  # noqa: U100
        raise NotImplementedError

    def handle_selected_arg_parse(self, options):
        selected = getattr(options, self.name)
        if selected not in self.possible:
            raise RuntimeError(f"No implementation for {self.interpreter}")
        self._impl_class = self.possible[selected]
        self.populate_selected_argparse(selected, options.app_data)
        return selected

    def populate_selected_argparse(self, selected, app_data):
        self.parser.description = f"options for {self.name} {selected}"
        self._impl_class.add_parser_arguments(self.parser, self.interpreter, app_data)

    def create(self, options):
        return self._impl_class(options, self.interpreter)


__all__ = [
    "PluginLoader",
    "ComponentBuilder",
]
