from ..command import Command


class SelfCommand(Command):

    name = "self"
    description = "Interact with Poetry directly."

    commands = []

    def handle(self):
        return self.call("help", self._config.name)
