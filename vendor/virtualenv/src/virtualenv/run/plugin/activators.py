from __future__ import absolute_import, unicode_literals

from argparse import ArgumentTypeError
from collections import OrderedDict
from importlib.metadata import EntryPoint

from .base import ComponentBuilder


class ActivationSelector(ComponentBuilder):
    _ENTRY_POINTS = {
        "virtualenv.activate": [
            EntryPoint(
                name=name,
                value=f"virtualenv.activation.{dst}",
                group="virtualenv.activate"
            ) for name, dst in [
                ("bash", "bash:BashActivator"),
                ("cshell", "cshell:CShellActivator"),
                ("batch", "batch:BatchActivator"),
                ("fish", "fish:FishActivator"),
                ("powershell", "powershell:PowerShellActivator"),
                ("python", "python:PythonActivator"),
                ("xonsh", "xonsh:XonshActivator")
            ]
        ]
    }

    def __init__(self, interpreter, parser):
        self.default = None
        possible = OrderedDict(
            (k, v) for k, v in self.options("virtualenv.activate").items() if v.supports(interpreter)
        )
        super(ActivationSelector, self).__init__(interpreter, parser, "activators", possible)
        self.parser.description = "options for activation scripts"
        self.active = None

    def add_selector_arg_parse(self, name, choices):
        self.default = ",".join(choices)
        self.parser.add_argument(
            "--{}".format(name),
            default=self.default,
            metavar="comma_sep_list",
            required=False,
            help="activators to generate - default is all supported",
            type=self._extract_activators,
        )

    def _extract_activators(self, entered_str):
        elements = [e.strip() for e in entered_str.split(",") if e.strip()]
        missing = [e for e in elements if e not in self.possible]
        if missing:
            raise ArgumentTypeError("the following activators are not available {}".format(",".join(missing)))
        return elements

    def handle_selected_arg_parse(self, options):
        selected_activators = (
            self._extract_activators(self.default) if options.activators is self.default else options.activators
        )
        self.active = {k: v for k, v in self.possible.items() if k in selected_activators}
        self.parser.add_argument(
            "--prompt",
            dest="prompt",
            metavar="prompt",
            help="provides an alternative prompt prefix for this environment",
            default=None,
        )
        for activator in self.active.values():
            activator.add_parser_arguments(self.parser, self.interpreter)

    def create(self, options):
        return [activator_class(options) for activator_class in self.active.values()]
