from __future__ import annotations

import os
from collections import OrderedDict

from virtualenv.activation.via_template import ViaTemplateActivator


class PythonActivator(ViaTemplateActivator):
    def templates(self):
        yield "activate_this.py.template"

    def _generate(self, replacements, templates, to_folder, creator):
        generated = []
        for template in templates:
            text = self.instantiate_template(replacements, template, creator)
            dest = to_folder / self.as_name(template).replace(".template", "")
            # use write_bytes to avoid platform specific line normalization (\n -> \r\n)
            dest.write_bytes(text.encode("utf-8"))
            generated.append(dest)
        return generated

    def replacements(self, creator, dest_folder):
        replacements = super().replacements(creator, dest_folder)
        lib_folders = OrderedDict((os.path.relpath(str(i), str(dest_folder)), None) for i in creator.libs)
        lib_folders = os.pathsep.join(lib_folders.keys()).replace("\\", "\\\\")  # escape Windows path characters
        replacements.update(
            {
                "__LIB_FOLDERS__": lib_folders,
                "__DECODE_PATH__": "",
            },
        )
        return replacements


__all__ = [
    "PythonActivator",
]
